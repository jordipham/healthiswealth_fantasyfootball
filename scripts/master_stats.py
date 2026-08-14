"""
compute_manager_master_stats.py

Reads owner_map.json plus ALL previously-computed derived files
(standings_archive.json, superlatives.json, hall_of_champions.json,
playoffs.json, rivalry_lanes.json, draft_day_profiler.json) and
collects EVERY statistical measure for each manager into one file:
data/derived/manager_master_stats.json.

This is NOT meant to power a page - it's a full archive/reference
dump for debugging, spot-checking, or just having one place to look
up everything known about a given manager, unlike manager_profiles.json
which is a curated, display-ready subset.

This is deliberately the LAST script in the pipeline - it depends on
every other compute_*.py having already been run.

Run with: python compute_manager_master_stats.py
(after: compute_standings_archive.py, compute_superlatives.py,
compute_hall_of_champions.py, compute_rivalries.py,
compute_draft_day_profiler.py, compute_playoffs.py)
"""

import json
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
DERIVED_DIR = os.path.join(SCRIPT_DIR, "..", "data", "derived")

STANDINGS_PATH = os.path.join(DERIVED_DIR, "standings_archive.json")
SUPERLATIVES_PATH = os.path.join(DERIVED_DIR, "superlatives.json")
HALL_PATH = os.path.join(DERIVED_DIR, "hall_of_champions.json")
RIVALRIES_PATH = os.path.join(DERIVED_DIR, "rivalry_lanes.json")
DRAFT_PATH = os.path.join(DERIVED_DIR, "draft_day_profiler.json")
PLAYOFFS_PATH = os.path.join(DERIVED_DIR, "playoffs.json")

OUTPUT_PATH = os.path.join(DERIVED_DIR, "manager_master_stats.json")


def load_json(path):
    if not os.path.exists(path):
        print(f"WARNING: {path} not found - run its compute script first. That section will be empty.")
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
# Standings history - every year's finish for this manager
# ---------------------------------------------------------------------------

def build_standings_history(standings_data, canonical_owners):
    by_manager = defaultdict(list)
    if not standings_data:
        return by_manager

    name_to_cid = {info["display_name"]: cid for cid, info in canonical_owners.items()}

    for year, year_data in standings_data.items():
        for row in year_data.get("standings", []):
            for name in (row.get("owners_display") or "").split(" & "):
                cid = name_to_cid.get(name)
                if cid:
                    by_manager[cid].append({
                        "year": int(year),
                        "final_standing": row.get("final_standing"),
                        "regular_season_seed": row.get("regular_season_seed"),
                        "league_size": year_data.get("league_size"),
                        "team_name": row.get("team_name"),
                        "record": row.get("record"),
                        "points_for": row.get("points_for"),
                        "points_against": row.get("points_against"),
                    })
    return by_manager


# ---------------------------------------------------------------------------
# Season record appearances - every season_records category this manager
# ever shows up in (from superlatives.json)
# ---------------------------------------------------------------------------

def build_season_record_appearances(superlatives_data, canonical_owners):
    by_manager = defaultdict(lambda: defaultdict(list))
    if not superlatives_data:
        return by_manager

    season_records = superlatives_data.get("season_records", {})

    for category, entries in season_records.items():
        for entry in entries:
            name = entry.get("owner_name")
            if name:
                # find cid by display name
                for cid, info in canonical_owners.items():
                    if info["display_name"] == name:
                        by_manager[cid][category].append(entry)
                        break

    return by_manager


# ---------------------------------------------------------------------------
# Full rivalry matchups involving this manager (not just highlights)
# ---------------------------------------------------------------------------

def build_full_rivalries(rivalry_data, canonical_owners):
    by_manager = defaultdict(list)
    if not rivalry_data:
        return by_manager

    for m in rivalry_data.get("matchups", []):
        for name in (m["manager_a"], m["manager_b"]):
            for cid, info in canonical_owners.items():
                if info["display_name"] == name:
                    by_manager[cid].append(m)
                    break

    return by_manager


# ---------------------------------------------------------------------------
# Full playoff game log for this manager (not just win/loss counts)
# ---------------------------------------------------------------------------

def build_full_playoff_games(playoffs_data, canonical_owners):
    by_manager = defaultdict(list)
    if not playoffs_data:
        return by_manager

    for year, brackets in playoffs_data.items():
        for bracket_type, games in brackets.items():
            for g in games:
                for side in ("home_owners_display", "away_owners_display"):
                    names = g.get(side)
                    if not names:
                        continue
                    for name in names.split(" & "):
                        for cid, info in canonical_owners.items():
                            if info["display_name"] == name:
                                by_manager[cid].append({
                                    "year": int(year),
                                    "bracket": bracket_type,
                                    **g,
                                })
                                break

    return by_manager


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def main():
    canonical_owners, id_to_canonical = load_owner_map()

    standings = load_json(STANDINGS_PATH)
    superlatives = load_json(SUPERLATIVES_PATH)
    hall = load_json(HALL_PATH)
    rivalries = load_json(RIVALRIES_PATH)
    draft = load_json(DRAFT_PATH)
    playoffs = load_json(PLAYOFFS_PATH)

    standings_history = build_standings_history(standings, canonical_owners)
    season_record_appearances = build_season_record_appearances(superlatives, canonical_owners)
    full_rivalries = build_full_rivalries(rivalries, canonical_owners)
    full_playoff_games = build_full_playoff_games(playoffs, canonical_owners)

    career_records = (superlatives or {}).get("career_records", {}).get("all_managers", {})
    draft_profiles = (draft or {}).get("manager_profiles", {})

    hall_entries_by_manager = defaultdict(list)
    if hall:
        for entry in hall:
            for owner in entry.get("owners", []):
                cid = owner.get("canonical_id")
                if cid:
                    hall_entries_by_manager[cid].append(entry)

    master = {}
    for cid, info in canonical_owners.items():
        master[cid] = {
            "owner_name": info["display_name"],
            "raw_owner_ids": info["owner_ids"],

            "career_totals": career_records.get(cid, {}),

            "standings_history": sorted(standings_history.get(cid, []), key=lambda x: x["year"]),

            "championship_entries": hall_entries_by_manager.get(cid, []),

            "playoff_games": sorted(full_playoff_games.get(cid, []), key=lambda x: (x["year"], x.get("week", 0))),

            "rivalries": full_rivalries.get(cid, []),

            "draft_profile_full": draft_profiles.get(cid, {}),

            "season_record_appearances": {
                k: v for k, v in season_record_appearances.get(cid, {}).items()
            },
        }

    os.makedirs(DERIVED_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(master, f, indent=2)

    print(f"Wrote master stats for {len(master)} managers to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    