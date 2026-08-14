"""
compute_draft_day_profiler.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json,
produces data/derived/draft_day_profiler.json - a per-manager draft
identity profile combining three angles:

  1. Draft value  - best value picks & biggest busts (round vs points)
  2. Retention     - kept vs dropped/traded away by season's end
  3. Signature picks - players drafted multiple times across years

Plus a league-wide "leaders" section (most loyal, biggest churner,
best pick ever, biggest bust ever).

Co-ownership handling: every pick and every roster is resolved to its
CREDITED owner(s) for that year via team_id, respecting the manual
exclusions in co_owner_overrides.json (training co-owners get no
credit for picks made or players kept on that team/year).

Known limitation: a player drafted, dropped, and never picked up by
ANYONE by season's end has no recoverable point total in this data -
box_scores() (needed for that) is current-season-only per ESPN's API,
confirmed via earlier testing. These picks are flagged explicitly
rather than silently skipped.

Pure read/compute/write - no ESPN API calls.

Run with: python compute_draft_day_profiler.py
"""

import json
import os
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "draft_day_profiler.json")

MIN_ROUND_FOR_BUST = 4     # rounds 1-4 count as "early" for bust detection
MIN_ROUND_FOR_STEAL = 8    # rounds 8+ count as "late" for steal detection
MIN_TIMES_FOR_SIGNATURE = 2  # drafted at least this many times to count as "signature"
TOP_N = 3


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


# ---------------------------------------------------------------------------
# Build per-year lookups: player_id -> (team_id, total_points) at season's end
# ---------------------------------------------------------------------------

def build_final_landing_spots(season_data):
    """
    Scans every team's final_roster for a season and maps each player_id
    to wherever they actually ended up (which may differ from who
    drafted them - dropped/traded/picked up elsewhere).
    """
    landing = {}
    for team in season_data.get("teams", []):
        tid = team.get("team_id")
        for p in team.get("final_roster", []) or []:
            pid = p.get("player_id")
            if pid is not None:
                landing[pid] = {
                    "team_id": tid,
                    "total_points": p.get("total_points"),
                    "position": p.get("position"),
                }
    return landing


# ---------------------------------------------------------------------------
# Build the full set of per-pick records, with drafted-by / ended-with resolved
# ---------------------------------------------------------------------------

def build_pick_records(history, id_to_canonical, canonical_owners, exclusions):
    records = []

    for year, season_data in history.get("seasons", {}).items():
        yr = int(year)
        teams_by_id = {t.get("team_id"): t for t in season_data.get("teams", [])}
        landing_spots = build_final_landing_spots(season_data)

        for pick in season_data.get("draft", []):
            drafted_team_id = pick.get("team_id")
            drafted_team = teams_by_id.get(drafted_team_id)
            if not drafted_team:
                continue

            drafted_by = resolve_credited_owners(drafted_team, yr, id_to_canonical, canonical_owners, exclusions)
            if not drafted_by:
                continue  # excluded co-owner drafted this - no credit, skip

            player_id = pick.get("player_id")
            landing = landing_spots.get(player_id)

            if landing is None:
                # Dropped and never picked up by anyone by season's end -
                # no recoverable point total in this data.
                ended_with = None
                total_points = None
                was_kept = False
                data_complete = False
            else:
                ended_team = teams_by_id.get(landing["team_id"])
                ended_with = resolve_credited_owners(ended_team, yr, id_to_canonical, canonical_owners, exclusions) if ended_team else []
                total_points = landing["total_points"]
                was_kept = (landing["team_id"] == drafted_team_id)
                data_complete = True

            for cid, name in drafted_by:
                records.append({
                    "year": yr,
                    "round_num": pick.get("round_num"),
                    "round_pick": pick.get("round_pick"),
                    "player_id": player_id,
                    "player_name": pick.get("player_name"),
                    "drafted_by_canonical_id": cid,
                    "drafted_by_name": name,
                    "ended_with": [n for _, n in ended_with] if landing else None,
                    "was_kept_by_drafter": was_kept,
                    "total_points": total_points,
                    "data_complete": data_complete,
                    "value_score": (total_points * pick.get("round_num", 1)) if total_points is not None and pick.get("round_num") else None,
                })

    return records


# ---------------------------------------------------------------------------
# Per-manager profile: value picks, retention, signature picks
# ---------------------------------------------------------------------------

def build_manager_profiles(pick_records):
    by_manager = defaultdict(list)
    for r in pick_records:
        by_manager[r["drafted_by_canonical_id"]].append(r)

    profiles = {}

    for cid, picks in by_manager.items():
        name = picks[0]["drafted_by_name"]

        complete_picks = [p for p in picks if p["data_complete"]]
        total_picks = len(picks)
        kept = sum(1 for p in complete_picks if p["was_kept_by_drafter"])
        incomplete = total_picks - len(complete_picks)

        # Retention rate is computed only over picks with a known landing spot
        retention_rate = round(kept / len(complete_picks), 4) if complete_picks else None

        # Best value: highest value_score
        valued = [p for p in complete_picks if p["value_score"] is not None]
        best_value = sorted(valued, key=lambda p: p["value_score"], reverse=True)[:TOP_N]

        # Biggest busts: early round (<= MIN_ROUND_FOR_BUST), lowest points
        early_picks = [p for p in complete_picks if p.get("round_num") and p["round_num"] <= MIN_ROUND_FOR_BUST and p["total_points"] is not None]
        busts = sorted(early_picks, key=lambda p: p["total_points"])[:TOP_N]

        # Best steals: late round (>= MIN_ROUND_FOR_STEAL), highest points
        late_picks = [p for p in complete_picks if p.get("round_num") and p["round_num"] >= MIN_ROUND_FOR_STEAL and p["total_points"] is not None]
        steals = sorted(late_picks, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

        # Signature picks: same player_id drafted multiple times by this manager
        by_player = defaultdict(list)
        for p in picks:
            by_player[p["player_id"]].append(p)

        signature = []
        for pid, instances in by_player.items():
            if len(instances) >= MIN_TIMES_FOR_SIGNATURE:
                career_points = sum(p["total_points"] for p in instances if p["total_points"] is not None)
                signature.append({
                    "player_name": instances[0]["player_name"],
                    "times_drafted": len(instances),
                    "years": sorted(p["year"] for p in instances),
                    "combined_points_across_those_seasons": round(career_points, 2),
                })
        signature = sorted(signature, key=lambda s: (s["times_drafted"], s["combined_points_across_those_seasons"]), reverse=True)[:TOP_N]

        profiles[cid] = {
            "owner_name": name,
            "total_picks": total_picks,
            "picks_with_incomplete_data": incomplete,
            "picks_kept": kept,
            "retention_rate": retention_rate,
            "best_value_picks": best_value,
            "biggest_busts": busts,
            "best_steals": steals,
            "signature_picks": signature,
        }

    return profiles


# ---------------------------------------------------------------------------
# League-wide leaders
# ---------------------------------------------------------------------------

def build_league_leaders(profiles, pick_records):
    with_retention = [p for p in profiles.values() if p["retention_rate"] is not None]

    def top_by(items, key, reverse=True, n=3):
        return sorted(items, key=lambda x: x[key], reverse=reverse)[:n]

    most_loyal = top_by(with_retention, "retention_rate", reverse=True)
    biggest_churner = top_by(with_retention, "retention_rate", reverse=False)

    complete = [r for r in pick_records if r["data_complete"] and r["value_score"] is not None]
    best_pick_ever = sorted(complete, key=lambda r: r["value_score"], reverse=True)[:TOP_N]

    early_complete = [r for r in complete if r.get("round_num") and r["round_num"] <= MIN_ROUND_FOR_BUST]
    worst_bust_ever = sorted(early_complete, key=lambda r: r["total_points"])[:TOP_N]

    return {
        "most_loyal_managers": most_loyal,
        "biggest_roster_churners": biggest_churner,
        "best_picks_in_league_history": best_pick_ever,
        "worst_busts_in_league_history": worst_bust_ever,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    pick_records = build_pick_records(history, id_to_canonical, canonical_owners, exclusions)
    profiles = build_manager_profiles(pick_records)
    leaders = build_league_leaders(profiles, pick_records)

    incomplete_count = sum(1 for r in pick_records if not r["data_complete"])

    output = {
        "manager_profiles": profiles,
        "league_leaders": leaders,
        "notes": {
            "picks_with_no_recoverable_landing_spot": incomplete_count,
            "explanation": "These players were drafted, dropped, and never picked up by anyone by season's end - ESPN's API does not expose retroactive week-by-week rosters, so no point total is recoverable for them.",
            "value_score_formula": "total_points * round_num (a simplification - rewards late-round picks that produced real points more than identical output from an early pick)",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(profiles)} manager profiles to {OUTPUT_PATH}")
    print(f"({incomplete_count} picks had no recoverable landing spot)")


if __name__ == "__main__":
    main()

    