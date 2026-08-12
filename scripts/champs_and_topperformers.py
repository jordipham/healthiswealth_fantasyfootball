"""
compute_hall_of_champions.py

Reads data/league_history.json (already pulled by gofetch.py) and
produces data/derived/hall_of_champions.json - one entry per year,
with that year's champion and their top performers by season points.

Co-ownership handling:
- By default, ALL co-owners on a team are credited for that season.
- co_owner_overrides.json lists specific exceptions where one co-owner
  was purely a training/learning participant and should receive NO
  credit - the other owner(s) get full solo credit instead. This is a
  manual, human-confirmed list, not something inferred automatically.

Pure read/compute/write - no ESPN API calls.

Run with: python compute_hall_of_champions.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "hall_of_champions.json")

TOP_N = 3


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
    """Returns a set of (year, raw_owner_id) tuples that should get NO stat credit."""
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


def resolve_all_owners(team, id_to_canonical, canonical_owners):
    """Full owners list, unfiltered - used for narrative/record-keeping only."""
    all_owners = team.get("all_owners") or []
    if not all_owners:
        oid = team.get("owner_id")
        cid, name = resolve_owner(oid, id_to_canonical, canonical_owners)
        return [{"canonical_id": cid, "display_name": name}] if cid else []

    resolved = []
    for o in all_owners:
        cid, name = resolve_owner(o.get("id"), id_to_canonical, canonical_owners)
        if cid is not None:
            resolved.append({"canonical_id": cid, "display_name": name})
    return resolved


def resolve_credited_owners(team, year, id_to_canonical, canonical_owners, exclusions):
    """
    Owners who should actually receive stat credit for this team/year -
    same as resolve_all_owners but with manually-confirmed training
    co-owners filtered out via co_owner_overrides.json.
    """
    all_owners = team.get("all_owners") or []
    if not all_owners:
        oid = team.get("owner_id")
        cid, name = resolve_owner(oid, id_to_canonical, canonical_owners)
        return [{"canonical_id": cid, "display_name": name}] if cid else []

    resolved = []
    for o in all_owners:
        raw_id = o.get("id")
        if (year, raw_id) in exclusions:
            continue  # confirmed training co-owner - no credit
        cid, name = resolve_owner(raw_id, id_to_canonical, canonical_owners)
        if cid is not None:
            resolved.append({"canonical_id": cid, "display_name": name})
    return resolved


# ---------------------------------------------------------------------------
# Champion + top performer logic
# ---------------------------------------------------------------------------

def get_champion(season_data):
    for team in season_data.get("teams", []):
        if team.get("final_standing") == 1:
            return team
    return None


def get_top_performers(team, n=TOP_N):
    roster = team.get("final_roster", []) or []
    valid = [p for p in roster if p.get("total_points") is not None]
    ranked = sorted(valid, key=lambda p: p["total_points"], reverse=True)
    return ranked[:n]


def build_hall_of_champions(history, id_to_canonical, canonical_owners, exclusions):
    seasons = history.get("seasons", {})
    hall = []

    for year in sorted(seasons.keys(), key=int):
        season_data = seasons[year]
        champion = get_champion(season_data)

        if champion is None:
            print(f"WARNING: no champion found for {year} (final_standing==1 missing) - skipping")
            continue

        credited_owners = resolve_credited_owners(champion, int(year), id_to_canonical, canonical_owners, exclusions)
        all_owners_of_record = resolve_all_owners(champion, id_to_canonical, canonical_owners)
        top_performers = get_top_performers(champion)

        hall.append({
            "year": int(year),
            "owners": credited_owners,
            "owners_display": " & ".join(o["display_name"] for o in credited_owners),
            "co_owned": len(credited_owners) > 1,
            "all_owners_of_record": all_owners_of_record,  # includes training co-owners, for transparency
            "team_name": champion.get("team_name"),
            "record": f"{champion.get('wins')}-{champion.get('losses')}-{champion.get('ties')}",
            "points_for": champion.get("points_for"),
            "points_against": champion.get("points_against"),
            "top_performers": [
                {
                    "player_name": p.get("player_name"),
                    "position": p.get("position"),
                    "pro_team": p.get("pro_team"),
                    "total_points": p.get("total_points"),
                    "avg_points": p.get("avg_points"),
                }
                for p in top_performers
            ],
        })

    return hall


def main():
    with open(INPUT_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    hall = build_hall_of_champions(history, id_to_canonical, canonical_owners, exclusions)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(hall, f, indent=2)

    print(f"Wrote {len(hall)} seasons to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    