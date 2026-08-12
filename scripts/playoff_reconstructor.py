"""
compute_playoffs.py

Reads data/league_history.json + owner_map.json, produces
data/derived/playoffs.json - a reconstructed playoff bracket per year,
organized by matchup_type (WINNERS_BRACKET, WINNERS_CONSOLATION_LADDER,
LOSERS_CONSOLATION_LADDER), with each game labeled by the teams'
pre-playoff seed (Team.standing - confirmed via direct data check to
be the regular-season seed, distinct from final_standing which is
the post-playoff result).

Pure read/compute/write - no ESPN API calls.

Run with: python compute_playoffs.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "playoffs.json")


# ---------------------------------------------------------------------------
# Owner resolution (same pattern as other compute_*.py scripts)
# ---------------------------------------------------------------------------

def load_owner_map():
    with open(OWNER_MAP_PATH) as f:
        raw = json.load(f)

    id_to_canonical = {}
    for canonical_id, info in raw["canonical_owners"].items():
        for oid in info["owner_ids"]:
            id_to_canonical[oid] = canonical_id

    return raw["canonical_owners"], id_to_canonical


def resolve_owner(owner_id, id_to_canonical, canonical_owners):
    canonical_id = id_to_canonical.get(owner_id)
    if canonical_id is None:
        return None, f"UNKNOWN ({owner_id})"
    return canonical_id, canonical_owners[canonical_id]["display_name"]


# ---------------------------------------------------------------------------
# Build a seed lookup (owner_id -> pre-playoff standing) for one season
# ---------------------------------------------------------------------------

def build_seed_lookup(season_data):
    lookup = {}
    for team in season_data.get("teams", []):
        owner_id = team.get("owner_id")
        if owner_id:
            lookup[owner_id] = team.get("standing")
    return lookup


# ---------------------------------------------------------------------------
# Per-year bracket reconstruction
# ---------------------------------------------------------------------------

def build_year_bracket(season_data, id_to_canonical, canonical_owners):
    seeds = build_seed_lookup(season_data)
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
                # Unknown/unexpected matchup_type - skip but don't crash,
                # this would be worth investigating if it ever prints.
                continue

            home_id = m.get("home_owner_id")
            away_id = m.get("away_owner_id")
            home_score = m.get("home_score")
            away_score = m.get("away_score")

            _, home_name = resolve_owner(home_id, id_to_canonical, canonical_owners)
            _, away_name = resolve_owner(away_id, id_to_canonical, canonical_owners)

            winner_name = None
            if home_score is not None and away_score is not None:
                if home_score > away_score:
                    winner_name = home_name
                elif away_score > home_score:
                    winner_name = away_name
                # else: tie, winner stays None

            brackets[matchup_type].append({
                "week": int(week),
                "home_owner_name": home_name,
                "home_seed": seeds.get(home_id),
                "home_score": home_score,
                "away_owner_name": away_name,
                "away_seed": seeds.get(away_id),
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

    output = {}
    for year, season_data in history.get("seasons", {}).items():
        bracket = build_year_bracket(season_data, id_to_canonical, canonical_owners)
        # Only include years that actually have playoff data
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

    