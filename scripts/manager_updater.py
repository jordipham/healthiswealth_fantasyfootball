"""
check_unmapped_owners.py

Run this after every gofetch.py pull, before running any compute_*.py
scripts. Flags any owner_id present in league_history.json that isn't
yet accounted for in owner_map.json - typically means a new manager
joined the league and needs to be added to the map.

Run with: python check_unmapped_owners.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")


def load_all_owner_ids_from_history(history):
    seen = {}  # owner_id -> (owner_name, set of years)
    for year, season_data in history.get("seasons", {}).items():
        for team in season_data.get("teams", []):
            oid = team.get("owner_id")
            name = team.get("owner_name")
            if oid is None:
                continue
            if oid not in seen:
                seen[oid] = (name, set())
            seen[oid][1].add(year)
    return seen


def load_mapped_owner_ids(owner_map):
    mapped = set()
    for canonical_id, info in owner_map.get("canonical_owners", {}).items():
        for oid in info.get("owner_ids", []):
            mapped.add(oid)
    return mapped


def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)
    with open(OWNER_MAP_PATH) as f:
        owner_map = json.load(f)

    all_ids = load_all_owner_ids_from_history(history)
    mapped_ids = load_mapped_owner_ids(owner_map)

    unmapped = {oid: info for oid, info in all_ids.items() if oid not in mapped_ids}

    if not unmapped:
        print("All owner_ids in league_history.json are accounted for in owner_map.json.")
        return

    print(f"Found {len(unmapped)} unmapped owner_id(s) - add these to owner_map.json:\n")
    for oid, (name, years) in unmapped.items():
        print(f'  "{oid}"  ->  name seen as "{name}", years: {sorted(years)}')

    print("\nAdd each as a new entry under \"canonical_owners\" in owner_map.json.")


if __name__ == "__main__":
    main()
