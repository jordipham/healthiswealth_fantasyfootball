"""
compute_rivalries.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json,
produces data/derived/rivalries.json - a full all-time head-to-head
matrix between every pair of managers, plus rivalry-specific
superlatives.

Co-ownership handling: joins matchups to teams via team_id, then
resolves only CREDITED owners per team/year (excluding confirmed
training co-owners from co_owner_overrides.json) before generating
head-to-head pairs. This means a training co-owner does NOT
accumulate rivalry games against anyone - only the real manager does.

Pure read/compute/write - no ESPN API calls.

Run with: python compute_rivalries.py
"""

import json
import os
from itertools import product

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "rivalry_lanes.json")

MIN_GAMES_FOR_SUPERLATIVES = 3


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


def pair_key(cid_a, cid_b):
    return tuple(sorted([cid_a, cid_b]))


# ---------------------------------------------------------------------------
# Build the full head-to-head matrix
# ---------------------------------------------------------------------------

def build_matrix(history, id_to_canonical, canonical_owners, exclusions):
    pairs = {}

    def get_pair(cid_a, name_a, cid_b, name_b):
        key = pair_key(cid_a, cid_b)
        if key not in pairs:
            pairs[key] = {
                "manager_a": {"canonical_id": key[0]},
                "manager_b": {"canonical_id": key[1]},
                "names": {cid_a: name_a, cid_b: name_b},
                "games": [],
                "wins": {cid_a: 0, cid_b: 0},
                "ties": 0,
                "points": {cid_a: 0.0, cid_b: 0.0},
            }
        return pairs[key]

    for year, season_data in history.get("seasons", {}).items():
        yr = int(year)
        teams_by_id = {t.get("team_id"): t for t in season_data.get("teams", [])}

        for week, matchups in season_data.get("matchups", {}).items():
            for m in matchups:
                if m.get("is_bye"):
                    continue

                home_score = m.get("home_score")
                away_score = m.get("away_score")
                if home_score is None or away_score is None:
                    continue

                home_team = teams_by_id.get(m.get("home_team_id"))
                away_team = teams_by_id.get(m.get("away_team_id"))
                if not home_team or not away_team:
                    continue

                home_owners = resolve_credited_owners(home_team, yr, id_to_canonical, canonical_owners, exclusions)
                away_owners = resolve_credited_owners(away_team, yr, id_to_canonical, canonical_owners, exclusions)

                for (cid_h, name_h), (cid_a, name_a) in product(home_owners, away_owners):
                    p = get_pair(cid_h, name_h, cid_a, name_a)

                    if home_score > away_score:
                        winner_cid = cid_h
                    elif away_score > home_score:
                        winner_cid = cid_a
                    else:
                        winner_cid = None

                    if winner_cid is None:
                        p["ties"] += 1
                    else:
                        p["wins"][winner_cid] += 1

                    p["points"][cid_h] += home_score
                    p["points"][cid_a] += away_score

                    p["games"].append({
                        "year": yr,
                        "week": int(week),
                        "is_playoff": m.get("is_playoff", False),
                        "matchup_type": m.get("matchup_type"),
                        cid_h: {"name": name_h, "score": home_score},
                        cid_a: {"name": name_a, "score": away_score},
                        "winner": name_h if winner_cid == cid_h else (name_a if winner_cid == cid_a else "TIE"),
                        "margin": round(abs(home_score - away_score), 2),
                    })

    return pairs


# ---------------------------------------------------------------------------
# Format the matrix into clean, frontend-ready entries
# ---------------------------------------------------------------------------

def format_pairs(pairs):
    formatted = []
    for key, p in pairs.items():
        cid_a, cid_b = key
        name_a = p["names"][cid_a]
        name_b = p["names"][cid_b]
        games_played = len(p["games"])
        wins_a = p["wins"][cid_a]
        wins_b = p["wins"][cid_b]

        formatted.append({
            "manager_a": name_a,
            "manager_b": name_b,
            "games_played": games_played,
            "wins_a": wins_a,
            "wins_b": wins_b,
            "ties": p["ties"],
            "points_a": round(p["points"][cid_a], 2),
            "points_b": round(p["points"][cid_b], 2),
            "win_pct_a": round(wins_a / games_played, 4) if games_played else None,
            "win_pct_gap": round(abs(wins_a - wins_b) / games_played, 4) if games_played else None,
            "games": sorted(p["games"], key=lambda g: (g["year"], g["week"])),
        })

    return formatted


# ---------------------------------------------------------------------------
# Rivalry-specific superlatives
# ---------------------------------------------------------------------------

def compute_rivalry_superlatives(formatted_pairs):
    eligible = [p for p in formatted_pairs if p["games_played"] >= MIN_GAMES_FOR_SUPERLATIVES]

    def top_by(items, key, reverse=True, n=3):
        return sorted(items, key=lambda x: x[key], reverse=reverse)[:n]

    most_lopsided = top_by(eligible, "win_pct_gap", reverse=True) if eligible else []
    closest_rivalry = top_by(eligible, "win_pct_gap", reverse=False) if eligible else []
    longest_running = top_by(formatted_pairs, "games_played", reverse=True)

    all_games_flat = []
    for p in formatted_pairs:
        for g in p["games"]:
            all_games_flat.append({
                "manager_a": p["manager_a"],
                "manager_b": p["manager_b"],
                "year": g["year"],
                "week": g["week"],
                "margin": g["margin"],
                "winner": g["winner"],
                "is_playoff": g["is_playoff"],
            })

    biggest_rivalry_blowout = sorted(all_games_flat, key=lambda g: g["margin"], reverse=True)[:3]
    closest_rivalry_game = sorted(all_games_flat, key=lambda g: g["margin"])[:3]

    return {
        "min_games_threshold": MIN_GAMES_FOR_SUPERLATIVES,
        "most_lopsided_rivalries": most_lopsided,
        "closest_rivalries": closest_rivalry,
        "longest_running_rivalries": longest_running,
        "biggest_single_game_blowouts": biggest_rivalry_blowout,
        "closest_single_games": closest_rivalry_game,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    pairs = build_matrix(history, id_to_canonical, canonical_owners, exclusions)
    formatted_pairs = format_pairs(pairs)
    superlatives = compute_rivalry_superlatives(formatted_pairs)

    output = {
        "matchups": formatted_pairs,
        "superlatives": superlatives,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(formatted_pairs)} head-to-head pairs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    