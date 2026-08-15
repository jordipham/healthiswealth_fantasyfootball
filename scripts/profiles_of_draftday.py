"""
compute_draft_day_profiler.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json,
produces data/derived/draft_day_profiler.json - a per-manager draft
identity profile combining four angles:

  1. Draft value  - best value picks & biggest busts (round vs points)
     ** QBs ARE EXCLUDED from this category. ** QBs are typically
     drafted late (common "wait on QB" strategy) but score heavily due
     to how fantasy points are weighted - so value_score's round_num
     multiplier structurally favors QBs regardless of actual skill in
     identifying them. Mixing them in made "Legendary" picks skew
     almost entirely QB, which isn't a meaningful signal.
  2. Captain at the Helm - QBs get their OWN category instead, ranked
     by raw total_points (not value_score - round-lateness bias is
     exactly what's being removed, so points-only is the fair,
     apples-to-apples comparison between QB seasons).
  3. Retention     - kept vs dropped/traded away by season's end
  4. Signature picks - players drafted multiple times across years
     (QBs remain eligible here - repeat-drafting is a personality/
     loyalty signal, not a value-mismatch issue, so no bias to remove)

Plus a league-wide "leaders" section (most loyal, biggest churner,
best pick ever [non-QB], biggest bust ever [non-QB], best QB campaign
ever).

Co-ownership handling: every pick and every roster is resolved to its
CREDITED owner(s) for that year via team_id, respecting the manual
exclusions in co_owner_overrides.json (training co-owners get no
credit for picks made or players kept on that team/year).

Known limitation: a player drafted, dropped, and never picked up by
ANYONE by season's end has no recoverable point total OR POSITION in
this data - position comes from final_roster, which only exists for
picks with a known landing spot. These picks are flagged explicitly
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

MIN_ROUND_FOR_BUST = 4
MIN_ROUND_FOR_STEAL = 8
MIN_TIMES_FOR_SIGNATURE = 2
TOP_N = 7
QB_POSITION = "QB"


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
# Build per-year lookups: player_id -> (team_id, total_points, position) at season's end
# ---------------------------------------------------------------------------

def build_final_landing_spots(season_data):
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
                continue

            player_id = pick.get("player_id")
            landing = landing_spots.get(player_id)

            if landing is None:
                ended_with = None
                total_points = None
                position = None
                was_kept = False
                data_complete = False
            else:
                ended_team = teams_by_id.get(landing["team_id"])
                ended_with = resolve_credited_owners(ended_team, yr, id_to_canonical, canonical_owners, exclusions) if ended_team else []
                total_points = landing["total_points"]
                position = landing["position"]
                was_kept = (landing["team_id"] == drafted_team_id)
                data_complete = True

            for cid, name in drafted_by:
                records.append({
                    "year": yr,
                    "round_num": pick.get("round_num"),
                    "round_pick": pick.get("round_pick"),
                    "player_id": player_id,
                    "player_name": pick.get("player_name"),
                    "position": position,
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
# Per-manager profile: value picks, QB spotlight, retention, signature picks
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
        retention_rate = round(kept / len(complete_picks), 4) if complete_picks else None

        # Non-QB pool for value/steal/bust categories - QBs structurally
        # inflate value_score regardless of actual draft skill, per the
        # module docstring above.
        non_qb_complete = [p for p in complete_picks if p["position"] != QB_POSITION]

        valued = [p for p in non_qb_complete if p["value_score"] is not None]
        best_value = sorted(valued, key=lambda p: p["value_score"], reverse=True)[:TOP_N]

        early_picks = [p for p in non_qb_complete if p.get("round_num") and p["round_num"] <= MIN_ROUND_FOR_BUST and p["total_points"] is not None]
        busts = sorted(early_picks, key=lambda p: p["total_points"])[:TOP_N]

        late_picks = [p for p in non_qb_complete if p.get("round_num") and p["round_num"] >= MIN_ROUND_FOR_STEAL and p["total_points"] is not None]
        steals = sorted(late_picks, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

        # Captain at the Helm: QB-only pool, ranked by raw total_points -
        # NOT value_score, since round-lateness bias is exactly what's
        # being removed. This is "who had the best QB season", full stop.
        qb_picks = [p for p in complete_picks if p["position"] == QB_POSITION and p["total_points"] is not None]
        captain_at_the_helm = sorted(qb_picks, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

        # Signature picks: unaffected by the QB bias issue - repeat-drafting
        # is a loyalty/personality signal regardless of position, so QBs
        # stay eligible here.
        by_player = defaultdict(list)
        for p in picks:
            by_player[p["player_id"]].append(p)

        signature = []
        for pid, instances in by_player.items():
            if len(instances) >= MIN_TIMES_FOR_SIGNATURE:
                career_points = sum(p["total_points"] for p in instances if p["total_points"] is not None)
                signature.append({
                    "player_name": instances[0]["player_name"],
                    "position": instances[0]["position"],
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
            "captain_at_the_helm": captain_at_the_helm,
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
    non_qb_complete = [r for r in complete if r["position"] != QB_POSITION]

    best_pick_ever = sorted(non_qb_complete, key=lambda r: r["value_score"], reverse=True)[:TOP_N]

    early_non_qb = [r for r in non_qb_complete if r.get("round_num") and r["round_num"] <= MIN_ROUND_FOR_BUST]
    worst_bust_ever = sorted(early_non_qb, key=lambda r: r["total_points"])[:TOP_N]

    qb_complete = [r for r in pick_records if r["data_complete"] and r["position"] == QB_POSITION and r["total_points"] is not None]
    best_qb_campaign_ever = sorted(qb_complete, key=lambda r: r["total_points"], reverse=True)[:TOP_N]

    return {
        "most_loyal_managers": most_loyal,
        "biggest_roster_churners": biggest_churner,
        "best_picks_in_league_history": best_pick_ever,
        "worst_busts_in_league_history": worst_bust_ever,
        "best_qb_campaigns_in_league_history": best_qb_campaign_ever,
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
            "explanation": "These players were drafted, dropped, and never picked up by anyone by season's end - ESPN's API does not expose retroactive week-by-week rosters, so no point total OR POSITION is recoverable for them.",
            "value_score_formula": "total_points * round_num (a simplification - rewards late-round picks that produced real points more than identical output from an early pick)",
            "qb_exclusion_note": "QBs are EXCLUDED from best_value_picks, best_steals, and biggest_busts (both per-manager and league-wide). QBs are typically drafted late but score heavily due to fantasy point weighting, so value_score structurally favors them regardless of actual draft skill. QBs get their own 'captain_at_the_helm' category instead, ranked by raw total_points.",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(profiles)} manager profiles to {OUTPUT_PATH}")
    print(f"({incomplete_count} picks had no recoverable landing spot)")


if __name__ == "__main__":
    main()

    