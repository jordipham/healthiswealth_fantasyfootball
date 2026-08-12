"""
compute_hall_of_champions.py

Reads data/league_history.json (already pulled by gofetch.py) and
produces data/derived/hall_of_champions.json - one entry per year,
with that year's champion (crediting ALL co-owners, not just the
primary owner) and their top performers by season points.

Pure read/compute/write - no ESPN API calls.

Run with: python compute_hall_of_champions.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
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


def resolve_owner(owner_id, id_to_canonical, canonical_owners):
    canonical_id = id_to_canonical.get(owner_id)
    if canonical_id is None:
        return None, f"UNKNOWN ({owner_id})"
    return canonical_id, canonical_owners[canonical_id]["display_name"]


def resolve_all_owners(team, id_to_canonical, canonical_owners):
    """
    Returns a list of {"canonical_id", "display_name"} for every owner
    on this team (primary + any co-owners), resolved through the
    canonical map. Falls back to the single primary owner if
    all_owners isn't present (older raw pulls).
    """
    all_owners = team.get("all_owners") or []
    if not all_owners:
        oid = team.get("owner_id")
        cid, name = resolve_owner(oid, id_to_canonical, canonical_owners)
        return [{"canonical_id": cid, "display_name": name}]

    resolved = []
    for o in all_owners:
        cid, name = resolve_owner(o.get("id"), id_to_canonical, canonical_owners)
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


def build_hall_of_champions(history, id_to_canonical, canonical_owners):
    seasons = history.get("seasons", {})
    hall = []

    for year in sorted(seasons.keys(), key=int):
        season_data = seasons[year]
        champion = get_champion(season_data)

        if champion is None:
            print(f"WARNING: no champion found for {year} (final_standing==1 missing) - skipping")
            continue

        owners = resolve_all_owners(champion, id_to_canonical, canonical_owners)
        top_performers = get_top_performers(champion)

        hall.append({
            "year": int(year),
            "owners": owners,
            "owners_display": " & ".join(o["display_name"] for o in owners),
            "co_owned": len(owners) > 1,
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
    hall = build_hall_of_champions(history, id_to_canonical, canonical_owners)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(hall, f, indent=2)

    print(f"Wrote {len(hall)} seasons to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    