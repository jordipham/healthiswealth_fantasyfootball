"""
compute_manager_profiles.py

Reads owner_map.json plus the FOUR previously-computed derived files
(superlatives.json, hall_of_champions.json, rivalry_lanes.json,
draft_day_profiler.json) and rolls them up into one combined profile
per manager: data/derived/manager_profiles.json.

This is deliberately the LAST script in the pipeline - it depends on
every other compute_*.py having already been run, since it reads
their outputs rather than league_history.json directly (except for a
small playoff-record calculation pulled from playoffs.json).

Run with: python compute_manager_profiles.py
(after: compute_superlatives.py, compute_hall_of_champions.py,
compute_rivalries.py, compute_draft_day_profiler.py, compute_playoffs.py)
"""

import json
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
DERIVED_DIR = os.path.join(SCRIPT_DIR, "..", "data", "derived")

SUPERLATIVES_PATH = os.path.join(DERIVED_DIR, "superlatives.json")
HALL_PATH = os.path.join(DERIVED_DIR, "hall_of_champions.json")
RIVALRIES_PATH = os.path.join(DERIVED_DIR, "rivalry_lanes.json")
PLAYOFFS_PATH = os.path.join(DERIVED_DIR, "playoffs.json")

OUTPUT_PATH = os.path.join(DERIVED_DIR, "manager_profiles.json")


def load_json(path):
    if not os.path.exists(path):
        print(f"WARNING: {path} not found - run its compute script first. Skipping that section.")
        return None
    with open(path) as f:
        return json.load(f)


def load_owner_map():
    with open(OWNER_MAP_PATH) as f:
        raw = json.load(f)
    id_to_canonical = {}
    for canonical_id, info in raw["canonical_owners"].items():
        for oid in info["owner_ids"]:
            id_to_canonical[oid] = canonical_id
    return raw["canonical_owners"], id_to_canonical


# ---------------------------------------------------------------------------
# Championships won (from hall_of_champions.json)
# ---------------------------------------------------------------------------

def build_championship_years(hall_data, canonical_owners):
    """Returns canonical_id -> list of years won."""
    by_manager = defaultdict(list)
    if not hall_data:
        return by_manager

    name_to_cid = {info["display_name"]: cid for cid, info in canonical_owners.items()}

    for entry in hall_data:
        for owner in entry.get("owners", []):
            cid = owner.get("canonical_id")
            if cid:
                by_manager[cid].append(entry["year"])
    return by_manager


# ---------------------------------------------------------------------------
# Rivalry highlights (from rivalry_lanes.json)
# ---------------------------------------------------------------------------

def build_rivalry_highlights(rivalry_data, canonical_owners):
    """
    For each manager, find: toughest rival (most losses TO one person),
    favorite opponent (most wins OVER one person), longest-running rivalry.
    """
    by_manager = defaultdict(list)
    if not rivalry_data:
        return {}

    name_to_cid = {info["display_name"]: cid for cid, info in canonical_owners.items()}

    for m in rivalry_data.get("matchups", []):
        a, b = m["manager_a"], m["manager_b"]
        by_manager[a].append({"opponent": b, "wins": m["wins_a"], "losses": m["wins_b"], "games": m["games_played"]})
        by_manager[b].append({"opponent": a, "wins": m["wins_b"], "losses": m["wins_a"], "games": m["games_played"]})

    highlights = {}
    for name, rivalries in by_manager.items():
        cid = name_to_cid.get(name)
        if not cid or not rivalries:
            continue

        toughest = max(rivalries, key=lambda r: r["losses"])
        favorite = max(rivalries, key=lambda r: r["wins"])
        longest = max(rivalries, key=lambda r: r["games"])

        highlights[cid] = {
            "toughest_rival": {"opponent": toughest["opponent"], "losses_to_them": toughest["losses"], "wins_over_them": toughest["wins"]},
            "favorite_opponent": {"opponent": favorite["opponent"], "wins_over_them": favorite["wins"], "losses_to_them": favorite["losses"]},
            "longest_running_rivalry": {"opponent": longest["opponent"], "total_games": longest["games"]},
        }

    return highlights


# ---------------------------------------------------------------------------
# Playoff record (from playoffs.json)
# ---------------------------------------------------------------------------

def build_playoff_records(playoffs_data, canonical_owners):
    """Returns canonical_id -> {appearances (distinct years), wins, losses}."""
    name_to_cid = {info["display_name"]: cid for cid, info in canonical_owners.items()}
    records = defaultdict(lambda: {"years": set(), "wins": 0, "losses": 0})

    if not playoffs_data:
        return {}

    for year, brackets in playoffs_data.items():
        for bracket_type, games in brackets.items():
            for g in games:
                home_names = g.get("home_owners_display")
                away_names = g.get("away_owners_display")
                winner = g.get("winner")

                for side_names in (home_names, away_names):
                    if not side_names:
                        continue
                    for name in side_names.split(" & "):
                        cid = name_to_cid.get(name)
                        if not cid:
                            continue
                        records[cid]["years"].add(int(year))
                        if winner == side_names:
                            records[cid]["wins"] += 1
                        elif winner is not None:
                            records[cid]["losses"] += 1

    return {
        cid: {
            "playoff_appearances": len(r["years"]),
            "playoff_wins": r["wins"],
            "playoff_losses": r["losses"],
        }
        for cid, r in records.items()
    }


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def main():
    canonical_owners, id_to_canonical = load_owner_map()

    superlatives = load_json(SUPERLATIVES_PATH)
    hall = load_json(HALL_PATH)
    rivalries = load_json(RIVALRIES_PATH)
    playoffs = load_json(PLAYOFFS_PATH)

    championship_years = build_championship_years(hall, canonical_owners)
    rivalry_highlights = build_rivalry_highlights(rivalries, canonical_owners)
    playoff_records = build_playoff_records(playoffs, canonical_owners)

    career_records = (superlatives or {}).get("career_records", {}).get("all_managers", {})

    profiles = {}
    for cid, info in canonical_owners.items():
        profiles[cid] = {
            "owner_name": info["display_name"],
            "status": info.get("status", "active"),
            "career": career_records.get(cid, {}),
            "championship_years": sorted(championship_years.get(cid, [])),
            "playoff_record": playoff_records.get(cid, {}),
            "rivalry_highlights": rivalry_highlights.get(cid, {}),
        }

    os.makedirs(DERIVED_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(profiles, f, indent=2)

    print(f"Wrote {len(profiles)} manager profiles to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    