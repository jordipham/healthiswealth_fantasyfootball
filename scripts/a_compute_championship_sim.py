"""
a_compute_championship_sim.py

Reads data/league_history.json + data/derived/hall_of_champions.json +
data/derived/playoffs.json, produces
data/raw_analytics/championship_sim.json.

MONTE CARLO REFRAME: rather than simulating a "remaining season" (which
doesn't apply to a finished league), this asks "how lucky was this
specific championship?" - for each year's actual playoff bracket, we
resample each game's outcome thousands of times using the two teams'
REAL regular-season scoring distributions (mean + stdev from that
season), and count how often the actual champion wins the bracket
under randomized-but-realistic weekly variance.

A champion who wins the simulation 90% of the time was a dominant,
deserved champion. One who wins only 15% of the time got a very lucky
bracket run - close games could easily have broken the other way.

Method per simulated trial, per playoff game:
  - Each team's simulated score = random draw from Normal(mean, stdev)
    using THEIR OWN regular-season mean/stdev that year.
  - Higher simulated score wins that game.
  - Winner advances through the same bracket structure the real
    playoffs used (byes preserved exactly as they really happened).

Pure Python's `random` module (Box-Muller transform for normal
sampling) - no numpy/scipy dependency needed for this.

Run with: python a_compute_championship_sim.py
"""

import json
import os
import random
import statistics
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
HALL_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "hall_of_champions.json")
PLAYOFFS_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "playoffs.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "raw_analytics", "championship_sim.json")

N_TRIALS = 10000


def load_owner_map():
    with open(OWNER_MAP_PATH) as f:
        raw = json.load(f)
    id_to_canonical = {}
    for canonical_id, info in raw["canonical_owners"].items():
        for oid in info["owner_ids"]:
            id_to_canonical[oid] = canonical_id
    return raw["canonical_owners"], id_to_canonical


def load_exclusions():
    if not os.path.exists(OVERRIDES_PATH):
        return set()
    with open(OVERRIDES_PATH) as f:
        raw = json.load(f)
    return {(e["year"], e["excluded_owner_id"]) for e in raw.get("exclusions", [])}


def resolve_owner(owner_id, id_to_canonical, canonical_owners):
    canonical_id = id_to_canonical.get(owner_id)
    if canonical_id is None:
        return None, f"UNKNOWN ({owner_id})"
    return canonical_id, canonical_owners[canonical_id]["display_name"]


def resolve_credited_owners(team, year, id_to_canonical, canonical_owners, exclusions):
    all_owners = team.get("all_owners") or []
    if not all_owners:
        oid = team.get("owner_id")
        cid, name = resolve_owner(oid, id_to_canonical, canonical_owners)
        return [(cid, name)] if cid else []
    resolved = []
    for o in all_owners:
        raw_id = o.get("id")
        if (year, raw_id) in exclusions:
            continue
        cid, name = resolve_owner(raw_id, id_to_canonical, canonical_owners)
        if cid is not None:
            resolved.append((cid, name))
    return resolved


def normal_sample(mean, stdev):
    """Box-Muller transform - avoids needing numpy for normal sampling."""
    if stdev <= 0:
        return mean
    u1, u2 = random.random(), random.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mean + z * stdev


def build_team_distributions(season_data):
    """team_id -> (mean, stdev) of that team's REGULAR SEASON scores."""
    reg_season_count = season_data.get("settings", {}).get("reg_season_count")
    dists = {}
    for team in season_data.get("teams", []):
        scores = (team.get("scores") or [])[:reg_season_count]
        valid = [s for s in scores if s]
        if len(valid) >= 2:
            dists[team["team_id"]] = (statistics.mean(valid), statistics.stdev(valid))
        elif valid:
            dists[team["team_id"]] = (valid[0], 0)
    return dists


def build_owner_to_team_id(season_data, year, id_to_canonical, canonical_owners, exclusions):
    """
    owners_display string -> team_id, for matching playoffs.json's
    name-based games back to a team. MUST use credited-owner resolution
    (same as compute_playoffs.py used to build those display strings) -
    NOT raw all_owners, or co-owned team-years (e.g. Jonathan Bi's
    2020-2021 seasons, credited solo after excluding training co-owner
    Saurab Nooguri) would fail to match, silently skipping real games.
    Confirmed this matters: Jared Tao's actual 2020 championship game
    was AGAINST exactly this kind of team.
    """
    mapping = {}
    for team in season_data.get("teams", []):
        credited = resolve_credited_owners(team, year, id_to_canonical, canonical_owners, exclusions)
        display = " & ".join(name for _, name in credited)
        if display:
            mapping[display] = team["team_id"]
    return mapping


def simulate_bracket(bracket_games, team_dists, owner_to_team_id, champion_display_name):
    """
    Runs N_TRIALS simulations of the WINNERS_BRACKET, resampling each
    game's outcome from the two teams' real scoring distributions.
    Returns the fraction of trials the actual champion wins ALL their
    games (i.e. wins the whole bracket).
    """
    champ_games = [
        g for g in bracket_games
        if g.get("home_owners_display") == champion_display_name or g.get("away_owners_display") == champion_display_name
    ]
    champ_games.sort(key=lambda g: g["week"])

    if not champ_games:
        return None, 0

    wins = 0
    for _ in range(N_TRIALS):
        champ_survives = True
        for g in champ_games:
            champ_is_home = g.get("home_owners_display") == champion_display_name
            opp_name = g.get("away_owners_display") if champ_is_home else g.get("home_owners_display")

            if not opp_name:
                continue  # bye - advances automatically, no game to simulate

            # playoffs.json only stores owner DISPLAY NAMES, not team_ids -
            # resolve both sides through the owner_to_team_id map built
            # from that season's real team roster.
            champ_tid = owner_to_team_id.get(champion_display_name)
            opp_tid = owner_to_team_id.get(opp_name)

            champ_dist = team_dists.get(champ_tid)
            opp_dist = team_dists.get(opp_tid)
            if not champ_dist or not opp_dist:
                continue  # missing data - skip this game, assume advance (defensive, shouldn't happen)

            champ_score = normal_sample(*champ_dist)
            opp_score = normal_sample(*opp_dist)

            if champ_score <= opp_score:
                champ_survives = False
                break

        if champ_survives:
            wins += 1

    return round(wins / N_TRIALS, 4), len(champ_games)


def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)
    with open(HALL_PATH) as f:
        hall = json.load(f)
    with open(PLAYOFFS_PATH) as f:
        playoffs = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    results = []

    for entry in hall:
        year = str(entry["year"])
        yr = entry["year"]
        season_data = history["seasons"].get(year)
        bracket = playoffs.get(year, {}).get("WINNERS_BRACKET", [])
        if not season_data or not bracket:
            continue

        team_dists = build_team_distributions(season_data)
        owner_to_team_id = build_owner_to_team_id(season_data, yr, id_to_canonical, canonical_owners, exclusions)

        win_probability, games_in_run = simulate_bracket(bracket, team_dists, owner_to_team_id, entry["owners_display"])

        if win_probability is None:
            continue

        results.append({
            "year": entry["year"],
            "champion": entry["owners_display"],
            "games_in_bracket_run": games_in_run,
            "simulated_championship_probability": win_probability,
            "luck_label": (
                "DOMINANT" if win_probability >= 0.6 else
                "DESERVED" if win_probability >= 0.35 else
                "LUCKY RUN" if win_probability >= 0.15 else
                "MIRACLE RUN"
            ),
        })

    output = {
        "simulations": results,
        "notes": {
            "method": f"{N_TRIALS} Monte Carlo trials per champion. Each playoff game's outcome is resampled from both teams' REAL regular-season scoring mean/stdev (Normal distribution, Box-Muller sampling) rather than assuming the real result was inevitable.",
            "interpretation": "simulated_championship_probability = fraction of simulated trials where the real champion wins their ENTIRE actual bracket path. Low probability doesn't mean they didn't deserve it - it means the games were close enough that variance could easily have gone the other way.",
            "luck_label_thresholds": "DOMINANT >=60%, DESERVED >=35%, LUCKY RUN >=15%, MIRACLE RUN <15%",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote championship simulations for {len(results)} seasons to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
