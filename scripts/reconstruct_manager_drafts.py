"""
reconstruct_manager_drafts.py

PERSONAL ANALYSIS TOOL - NOT part of the site pipeline, does not feed
any page. Reconstructs each manager's first 10 draft picks, every
year, formatted differently depending on that year's draft type:

  SNAKE:   "Round #: Player Name, POSITION" - in actual pick order
  AUCTION: ranked by bid amount, most to least expensive

DEPENDS on the gofetch.py position-enrichment fix - every pick needs
pick["position"] populated directly, which only exists after rerunning
the updated gofetch.py.

Output: both a human-readable printed report AND a structured JSON
file (data/personal_analysis/manager_draft_reconstructions.json) for
whatever tendency analysis comes next - kept in its own folder,
deliberately separate from data/derived/ and data/raw_analytics/,
since none of this is meant to reach the public site.

Run with: python reconstruct_manager_drafts.py
"""

import json
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
DRAFT_TYPE_PATH = os.path.join(SCRIPT_DIR, "draft_type_tracker.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "personal_analysis", "manager_draft_reconstructions.json")

FIRST_N_PICKS = 10


# ---------------------------------------------------------------------------
# Owner resolution (same pattern as every other compute_*.py script)
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


def load_draft_types():
    if not os.path.exists(DRAFT_TYPE_PATH):
        return {}
    with open(DRAFT_TYPE_PATH) as f:
        raw = json.load(f)
    return {year: info["draft_type"] for year, info in raw.get("years", {}).items()}


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


# ---------------------------------------------------------------------------
# Build: for each (canonical_id, year), their picks in draft order
# ---------------------------------------------------------------------------

def build_manager_year_picks(history, id_to_canonical, canonical_owners, exclusions, draft_types):
    result = defaultdict(dict)  # canonical_id -> {year: [picks]}

    for year, season_data in history.get("seasons", {}).items():
        teams_by_id = {t["team_id"]: t for t in season_data.get("teams", [])}
        draft_type = draft_types.get(year, "snake")

        picks_by_team = defaultdict(list)
        for pick in season_data.get("draft", []):
            picks_by_team[pick["team_id"]].append(pick)

        for team_id, picks in picks_by_team.items():
            team = teams_by_id.get(team_id)
            if not team:
                continue
            credited = resolve_credited_owners(team, int(year), id_to_canonical, canonical_owners, exclusions)

            if draft_type == "snake":
                ordered = sorted(picks, key=lambda p: (p.get("round_num") or 999))
            else:  # auction
                ordered = sorted(picks, key=lambda p: (p.get("bid_amount") or 0), reverse=True)

            top_picks = ordered[:FIRST_N_PICKS]

            for cid, name in credited:
                if cid is None:
                    continue
                result[cid][year] = {
                    "owner_name": name,
                    "draft_type": draft_type,
                    "picks": top_picks,
                }

    return result


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_snake_line(pick):
    pos = pick.get("position") or "?"
    name = pick.get("player_name") or "UNKNOWN"
    return f"  Round {pick.get('round_num')}: {name}, {pos}"


def format_auction_line(rank, pick):
    pos = pick.get("position") or "?"
    name = pick.get("player_name") or "UNKNOWN"
    bid = pick.get("bid_amount")
    bid_str = f"${bid}" if bid is not None else "$?"
    return f"  #{rank}: {name}, {pos} ({bid_str})"


def print_report(manager_year_picks, canonical_owners):
    for cid in sorted(manager_year_picks.keys(), key=lambda c: canonical_owners[c]["display_name"]):
        name = canonical_owners[cid]["display_name"]
        print(f"\n{'=' * 60}\n{name.upper()}\n{'=' * 60}")

        for year in sorted(manager_year_picks[cid].keys()):
            entry = manager_year_picks[cid][year]
            print(f"\n{year} ({entry['draft_type'].upper()} DRAFT):")

            if entry["draft_type"] == "snake":
                for pick in entry["picks"]:
                    print(format_snake_line(pick))
            else:
                for i, pick in enumerate(entry["picks"], start=1):
                    print(format_auction_line(i, pick))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()
    draft_types = load_draft_types()

    manager_year_picks = build_manager_year_picks(history, id_to_canonical, canonical_owners, exclusions, draft_types)

    print_report(manager_year_picks, canonical_owners)

    # Also write structured JSON for future tendency analysis
    output = {}
    for cid, years in manager_year_picks.items():
        output[cid] = {
            "owner_name": canonical_owners[cid]["display_name"],
            "years": years,
        }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n\nAlso wrote structured JSON to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
