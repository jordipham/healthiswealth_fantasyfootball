"""
check_unmapped_owners.py

Run this after every gofetch.py pull, before running any compute_*.py
scripts. Flags any owner_id present in league_history.json that isn't
yet accounted for in owner_map.json.

Checks ALL owners per team (team["all_owners"]), not just the primary
owner - otherwise a co-owner (e.g. someone added as a secondary owner
on a friend's team) could go completely undetected, the way Jonathan
Bi's 2020-2021 co-ownership did before this fix.

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
            all_owners = team.get("all_owners")
            if not all_owners:
                # Fallback for raw data pulled before all_owners existed
                oid = team.get("owner_id")
                name = team.get("owner_name")
                all_owners = [{"id": oid, "name": name}] if oid else []

            for o in all_owners:
                oid = o.get("id")
                name = o.get("name")
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
        print("All owner_ids (including co-owners) in league_history.json are accounted for in owner_map.json.")
        return

    print(f"Found {len(unmapped)} unmapped owner_id(s) - add these to owner_map.json:\n")
    for oid, (name, years) in unmapped.items():
        print(f'  "{oid}"  ->  name seen as "{name}", years: {sorted(years)}')

    print("\nAdd each as a new entry under \"canonical_owners\" in owner_map.json.")
    print("If this id belongs to someone already mapped (e.g. found as a co-owner")
    print("under a different account), add it to their EXISTING owner_ids list instead")
    print("of creating a new person - same pattern as Justin Lee's merged entry.")


if __name__ == "__main__":
    main()

    