"""
compute_performance_patterns.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json,
produces data/raw_analytics/performance_patterns.json.

TWO ANALYSES, both scoped to REGULAR SEASON weeks only (playoffs are
single-elimination brackets, not full round-robin against the whole
league, so they don't have the same interpretive meaning for either
of these stats - mixing them in would skew results unfairly for
managers who played more/fewer playoff games than others).

1. LUCK VS SKILL (expected wins)
   For every regular-season week, rank a manager's score against every
   OTHER team's score that same week. Their "expected win fraction"
   that week = the fraction of opponents they would have beaten had
   they faced them, not just their actual real opponent. Summed
   across the season = expected_wins. Compare to actual wins (from
   the real schedule) to get a luck_differential: positive means they
   won more than their scoring output alone would predict (favorable
   schedule / clutch performance), negative means the opposite.

2. CONSISTENCY / VOLATILITY
   Standard deviation of a manager's regular-season weekly scores.
   Also computes coefficient_of_variation (stdev / mean) so it's
   comparable ACROSS seasons/eras where average scoring levels differ
   (e.g. league-wide scoring inflation over the years) - two managers
   could have the same stdev but very different "riskiness" if their
   average score levels differ.

IMPORTANT: team.scores arrays include ALL weeks (regular season +
playoffs) - confirmed by checking real data where len(scores)=17 but
reg_season_count=14. Every computation here explicitly slices to
scores[:reg_season_count].

Co-ownership handling: identical pattern to every other compute_*.py
script - stats credited only to resolve_credited_owners(), respecting
co_owner_overrides.json exclusions.

Pure read/compute/write - no ESPN API calls, no external dependencies.

Run with: python compute_performance_patterns.py
"""

import json
import os
import statistics
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "raw_analytics", "performance_patterns.json")


# ---------------------------------------------------------------------------
# Owner resolution (same pattern as every other compute_*.py script)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Per-season computation
# ---------------------------------------------------------------------------

def compute_season(season_data, year, id_to_canonical, canonical_owners, exclusions):
    reg_season_count = season_data.get("settings", {}).get("reg_season_count")
    if not reg_season_count:
        return {}

    teams = season_data.get("teams", [])

    # Build: week_index -> [(team_id, score), ...] for every team with a
    # real regular-season score that week
    weekly_scores_by_team = {}
    for team in teams:
        scores = team.get("scores") or []
        reg_scores = scores[:reg_season_count]
        weekly_scores_by_team[team["team_id"]] = reg_scores

    week_pools = defaultdict(list)  # week_idx -> [(team_id, score)]
    for team_id, reg_scores in weekly_scores_by_team.items():
        for week_idx, score in enumerate(reg_scores):
            if score:  # skip 0/missing - shouldn't happen in reg season, but defensive
                week_pools[week_idx].append((team_id, score))

    # Compute expected win fraction for each team, each week
    expected_wins_by_team = defaultdict(float)
    for week_idx, pool in week_pools.items():
        for team_id, score in pool:
            others = [s for tid, s in pool if tid != team_id]
            if not others:
                continue
            beats = sum(1 for s in others if score > s)
            ties = sum(1 for s in others if score == s)
            expected_wins_by_team[team_id] += (beats + 0.5 * ties) / len(others)

    result = {}
    for team in teams:
        tid = team["team_id"]
        credited = resolve_credited_owners(team, year, id_to_canonical, canonical_owners, exclusions)
        reg_scores = weekly_scores_by_team.get(tid, [])
        valid_scores = [s for s in reg_scores if s]

        actual_wins = team.get("wins", 0) or 0
        expected_wins = round(expected_wins_by_team.get(tid, 0.0), 2)
        luck_differential = round(actual_wins - expected_wins, 2)

        score_stdev = round(statistics.stdev(valid_scores), 2) if len(valid_scores) >= 2 else None
        score_mean = round(statistics.mean(valid_scores), 2) if valid_scores else None
        coefficient_of_variation = round(score_stdev / score_mean, 4) if score_stdev and score_mean else None

        for cid, name in credited:
            if cid is None:
                continue
            result[cid] = {
                "owner_name": name,
                "actual_wins": actual_wins,
                "expected_wins": expected_wins,
                "luck_differential": luck_differential,
                "score_stdev": score_stdev,
                "score_mean": score_mean,
                "coefficient_of_variation": coefficient_of_variation,
                "weekly_scores": valid_scores,
            }

    return result


# ---------------------------------------------------------------------------
# Career aggregation - pools every regular-season week across every year
# ---------------------------------------------------------------------------

def compute_career(seasons_output):
    career = defaultdict(lambda: {
        "owner_name": None,
        "actual_wins": 0,
        "expected_wins": 0.0,
        "all_weekly_scores": [],
    })

    for year, managers in seasons_output.items():
        for cid, m in managers.items():
            c = career[cid]
            c["owner_name"] = m["owner_name"]
            c["actual_wins"] += m["actual_wins"]
            c["expected_wins"] += m["expected_wins"]
            c["all_weekly_scores"].extend(m["weekly_scores"])

    result = {}
    for cid, c in career.items():
        scores = c["all_weekly_scores"]
        stdev = round(statistics.stdev(scores), 2) if len(scores) >= 2 else None
        mean = round(statistics.mean(scores), 2) if scores else None
        cv = round(stdev / mean, 4) if stdev and mean else None

        result[cid] = {
            "owner_name": c["owner_name"],
            "actual_wins": c["actual_wins"],
            "expected_wins": round(c["expected_wins"], 2),
            "luck_differential": round(c["actual_wins"] - c["expected_wins"], 2),
            "score_stdev": stdev,
            "score_mean": mean,
            "coefficient_of_variation": cv,
            "total_regular_season_games": len(scores),
        }

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    seasons_output = {}
    for year, season_data in history.get("seasons", {}).items():
        seasons_output[year] = compute_season(season_data, int(year), id_to_canonical, canonical_owners, exclusions)

    career_output = compute_career(seasons_output)

    # Strip weekly_scores from the season-level output before writing -
    # it was only needed internally to build career aggregates, and
    # including 17 years x 15 managers x ~14 raw scores would bloat the
    # file for no frontend benefit (the frontend only needs the computed
    # stats, not the raw inputs).
    for year, managers in seasons_output.items():
        for m in managers.values():
            del m["weekly_scores"]

    output = {
        "seasons": seasons_output,
        "career": career_output,
        "notes": {
            "scope": "Regular season weeks only - playoff weeks are excluded from both analyses, since playoffs are single-elimination brackets, not full round-robin against the whole league.",
            "expected_wins_method": "For each week, a team's expected win fraction = (number of OTHER teams they outscored + 0.5 x ties) / (total other teams that week). Summed across the season.",
            "luck_differential_interpretation": "actual_wins - expected_wins. Positive = won more than their scoring output predicts. Negative = scored well but still lost more than expected (tough schedule luck).",
            "coefficient_of_variation_purpose": "score_stdev / score_mean - makes volatility comparable across seasons/eras with different average scoring levels.",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote performance patterns for {len(seasons_output)} seasons, {len(career_output)} career profiles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
