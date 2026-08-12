"""
compute_playoffs.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json,
produces data/derived/playoffs.json - a reconstructed playoff bracket per
year, crediting only confirmed real managers (training co-owners listed
in co_owner_overrides.json are excluded from credit but still available
in all_owners_of_record for transparency).

Uses team_id (not owner_id) to join matchups back to their teams, so
co-ownership is handled correctly regardless of which owner ESPN
listed as "primary" that season.

Pure read/compute/write - no ESPN API calls.

Run with: python compute_playoffs.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "playoffs.json")


# ---------------------------------------------------------------------------
# Owner resolution
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
        return [{"canonical_id": cid, "display_name": name}] if cid else []

    resolved = []
    for o in all_owners:
        raw_id = o.get("id")
        if (year, raw_id) in exclusions:
            continue
        cid, name = resolve_owner(raw_id, id_to_canonical, canonical_owners)
        if cid is not None:
            resolved.append({"canonical_id": cid, "display_name": name})
    return resolved


def owners_display(resolved_owners):
    return " & ".join(o["display_name"] for o in resolved_owners)


# ---------------------------------------------------------------------------
# Build lookups (team_id -> seed, team_id -> credited owners) for one season
# ---------------------------------------------------------------------------

def build_team_lookups(season_data, year, id_to_canonical, canonical_owners, exclusions):
    seeds = {}
    owners_by_team = {}
    for team in season_data.get("teams", []):
        tid = team.get("team_id")
        seeds[tid] = team.get("standing")
        owners_by_team[tid] = resolve_credited_owners(team, year, id_to_canonical, canonical_owners, exclusions)
    return seeds, owners_by_team


# ---------------------------------------------------------------------------
# Per-year bracket reconstruction
# ---------------------------------------------------------------------------

def build_year_bracket(season_data, year, id_to_canonical, canonical_owners, exclusions):
    seeds, owners_by_team = build_team_lookups(season_data, year, id_to_canonical, canonical_owners, exclusions)
    matchups = season_data.get("matchups", {})

    brackets = {
        "WINNERS_BRACKET": [],
        "WINNERS_CONSOLATION_LADDER": [],
        "LOSERS_CONSOLATION_LADDER": [],
    }

    for week, week_matchups in sorted(matchups.items(), key=lambda x: int(x[0])):
        for m in week_matchups:
            if not m.get("is_playoff"):
                continue

            matchup_type = m.get("matchup_type")
            if matchup_type not in brackets:
                continue

            home_team_id = m.get("home_team_id")
            away_team_id = m.get("away_team_id")
            home_score = m.get("home_score")
            away_score = m.get("away_score")

            home_owners = owners_by_team.get(home_team_id, [])
            away_owners = owners_by_team.get(away_team_id, [])
            home_name = owners_display(home_owners) if home_owners else None
            away_name = owners_display(away_owners) if away_owners else None

            winner_name = None
            if home_score is not None and away_score is not None:
                if home_score > away_score:
                    winner_name = home_name
                elif away_score > home_score:
                    winner_name = away_name

            brackets[matchup_type].append({
                "week": int(week),
                "home_owners": home_owners,
                "home_owners_display": home_name,
                "home_co_owned": len(home_owners) > 1,
                "home_seed": seeds.get(home_team_id),
                "home_score": home_score,
                "away_owners": away_owners,
                "away_owners_display": away_name,
                "away_co_owned": len(away_owners) > 1,
                "away_seed": seeds.get(away_team_id),
                "away_score": away_score,
                "winner": winner_name,
            })

    return brackets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    output = {}
    for year, season_data in history.get("seasons", {}).items():
        bracket = build_year_bracket(season_data, int(year), id_to_canonical, canonical_owners, exclusions)
        if any(bracket.values()):
            output[year] = bracket
        else:
            print(f"No playoff matchup_type data found for {year} - skipping")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote playoff brackets for {len(output)} seasons to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    