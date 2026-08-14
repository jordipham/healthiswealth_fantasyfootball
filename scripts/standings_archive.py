"""
compute_standings_archive.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json,
produces data/derived/standings_archive.json - a clean year-by-year
final standings table for every season, crediting only real managers
(training co-owners excluded per co_owner_overrides.json).

Pure read/compute/write - no ESPN API calls.

Run with: python compute_standings_archive.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "standings_archive.json")


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
        return [name] if cid else []

    resolved = []
    for o in all_owners:
        raw_id = o.get("id")
        if (year, raw_id) in exclusions:
            continue
        cid, name = resolve_owner(raw_id, id_to_canonical, canonical_owners)
        if cid is not None:
            resolved.append(name)
    return resolved


def build_standings(history, id_to_canonical, canonical_owners, exclusions):
    output = {}

    for year, season_data in history.get("seasons", {}).items():
        yr = int(year)
        teams = season_data.get("teams", [])

        rows = []
        for t in teams:
            owners = resolve_credited_owners(t, yr, id_to_canonical, canonical_owners, exclusions)
            rows.append({
                "final_standing": t.get("final_standing"),
                "regular_season_seed": t.get("standing"),
                "owners_display": " & ".join(owners) if owners else "UNKNOWN",
                "team_name": t.get("team_name"),
                "record": f"{t.get('wins')}-{t.get('losses')}-{t.get('ties')}",
                "points_for": t.get("points_for"),
                "points_against": t.get("points_against"),
                "is_champion": t.get("final_standing") == 1,
            })

        rows.sort(key=lambda r: r["final_standing"] if r["final_standing"] is not None else 999)

        output[year] = {
            "league_size": len(teams),
            "standings": rows,
        }

    return output


def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    standings = build_standings(history, id_to_canonical, canonical_owners, exclusions)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(standings, f, indent=2)

    print(f"Wrote standings for {len(standings)} seasons to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    