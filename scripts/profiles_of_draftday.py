"""
compute_draft_day_profiler.py

Reads data/league_history.json + owner_map.json + co_owner_overrides.json
+ scripts/draft_type_tracker.json, produces
data/derived/draft_day_profiler.json.

DRAFT ERA SPLIT: draft_type_tracker.json manually declares each year as
"snake" or "auction" (bid_amount alone isn't reliable enough to trust
blindly forever - a human confirms it, same reasoning as
co_owner_overrides.json). Every value-based category is computed
SEPARATELY per era, since round_num-based value_score and
dollar-based cost-efficiency are not comparable numbers:

  SNAKE ERA                          AUCTION ERA
  ----------------------------------------------------------
  Best Value: value_score            Best Value: points-per-dollar
  Best Steals: high pts, late round  Best Steals: high pts, cheap bid
  Stars: high pts, early round       Stars: high pts, expensive bid
  Busts: low pts, early round        Busts: low pts, expensive bid

Cheap/expensive bid thresholds are DYNAMIC - computed fresh each run
from that year's actual bid_amount distribution (25th/75th percentile
split), not hardcoded, so the categories self-adjust if auction
budgets or spending patterns change in future seasons.

UNCHANGED, NOT era-split (these metrics aren't round/price-dependent):
  - Captain at the Helm (QB) - ranked by raw total_points
  - Signature Picks - repeat-draft frequency, not value
  - Retention rate - whole-career stat

Known limitation: a player drafted, dropped, and never picked up by
ANYONE by season's end has no recoverable point total OR POSITION -
box_scores()/final_roster data doesn't exist for them.

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
DRAFT_TYPE_PATH = os.path.join(SCRIPT_DIR, "draft_type_tracker.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "draft_day_profiler.json")

MIN_ROUND_FOR_BUST = 4
MIN_ROUND_FOR_STEAL = 8
MIN_TIMES_FOR_SIGNATURE = 2
TOP_N = 5
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


def load_draft_types():
    """Returns {year_str: 'snake'|'auction'}. Missing years default to 'snake'."""
    if not os.path.exists(DRAFT_TYPE_PATH):
        print("WARNING: draft_type_tracker.json not found - assuming all years are snake drafts.")
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
# Build per-year lookups: player_id -> (team_id, total_points, position)
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
# Build the full set of per-pick records, with draft_type + bid_amount added
# ---------------------------------------------------------------------------

def build_pick_records(history, id_to_canonical, canonical_owners, exclusions, draft_types):
    records = []

    for year, season_data in history.get("seasons", {}).items():
        yr = int(year)
        draft_type = draft_types.get(year, "snake")
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
            bid_amount = pick.get("bid_amount")

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

            value_score = None
            points_per_dollar = None
            if total_points is not None:
                if draft_type == "snake" and pick.get("round_num"):
                    value_score = total_points * pick.get("round_num", 1)
                elif draft_type == "auction" and bid_amount:
                    points_per_dollar = total_points / bid_amount

            for cid, name in drafted_by:
                records.append({
                    "year": yr,
                    "draft_type": draft_type,
                    "round_num": pick.get("round_num"),
                    "round_pick": pick.get("round_pick"),
                    "bid_amount": bid_amount,
                    "player_id": player_id,
                    "player_name": pick.get("player_name"),
                    "position": position,
                    "drafted_by_canonical_id": cid,
                    "drafted_by_name": name,
                    "ended_with": [n for _, n in ended_with] if landing else None,
                    "was_kept_by_drafter": was_kept,
                    "total_points": total_points,
                    "data_complete": data_complete,
                    "value_score": value_score,
                    "points_per_dollar": points_per_dollar,
                })

    return records


# ---------------------------------------------------------------------------
# Dynamic cheap/expensive bid thresholds - computed fresh from real data
# ---------------------------------------------------------------------------

def compute_bid_thresholds(pick_records):
    """
    Returns (cheap_cutoff, expensive_cutoff) computed from the 25th/75th
    percentile of all real auction bid_amounts across the whole dataset.
    Dynamic on purpose - self-adjusts if budgets/spending patterns change
    in future seasons, rather than a hardcoded dollar figure.
    """
    bids = sorted(
        r["bid_amount"] for r in pick_records
        if r["draft_type"] == "auction" and r["bid_amount"] is not None and r["bid_amount"] > 0
    )
    if not bids:
        return None, None

    n = len(bids)
    cheap_cutoff = bids[int(n * 0.25)]
    expensive_cutoff = bids[int(n * 0.75)]
    return cheap_cutoff, expensive_cutoff


def compute_rarity_thresholds(pick_records):
    """
    Computes Junk/Common/Rare/Legendary cutoffs SEPARATELY for each era,
    dynamically from the real distribution each run - not hardcoded.
    This replaces the old pattern where snake thresholds were hardcoded
    constants in the JS file (which is exactly what caused a real bug
    earlier: removing QBs from the pool shifted the distribution, and
    the hardcoded JS thresholds silently went stale until manually
    caught and recalibrated). Storing computed thresholds in the JSON
    output means the frontend never needs manual recalibration again -
    it just reads whatever the backend computed this run.

    SNAKE tier is based on value_score (points x round_num).
    AUCTION tier is based on points_per_dollar.
    Both pools exclude QBs, same reasoning as everywhere else - QBs
    structurally skew both formulas regardless of the era.
    """
    def percentile_thresholds(values):
        values = sorted(v for v in values if v is not None and v > 0)
        if not values:
            return None
        n = len(values)
        return {
            "junk": values[int(n * 0.25)],
            "common": values[int(n * 0.50)],
            "rare": values[int(n * 0.75)],
        }

    snake_scores = [
        r["value_score"] for r in pick_records
        if r["draft_type"] == "snake" and r["data_complete"]
        and r["position"] != QB_POSITION and r["value_score"] is not None
    ]
    auction_scores = [
        r["points_per_dollar"] for r in pick_records
        if r["draft_type"] == "auction" and r["data_complete"]
        and r["position"] != QB_POSITION and r["points_per_dollar"] is not None
    ]

    return {
        "snake": percentile_thresholds(snake_scores),
        "auction": percentile_thresholds(auction_scores),
    }


# ---------------------------------------------------------------------------
# Per-manager profile: era-split value picks, QB spotlight, retention, signature
# ---------------------------------------------------------------------------

def build_era_categories(picks, era, cheap_cutoff, expensive_cutoff):
    """Builds best_value/best_steals/stars/biggest_busts for ONE era's picks."""
    complete = [p for p in picks if p["data_complete"] and p["draft_type"] == era]
    non_qb = [p for p in complete if p["position"] != QB_POSITION]

    if era == "snake":
        valued = [p for p in non_qb if p["value_score"] is not None]
        best_value = sorted(valued, key=lambda p: p["value_score"], reverse=True)[:TOP_N]

        early = [p for p in non_qb if p.get("round_num") and p["round_num"] <= MIN_ROUND_FOR_BUST and p["total_points"] is not None]
        busts = sorted(early, key=lambda p: p["total_points"])[:TOP_N]
        stars = sorted(early, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

        late = [p for p in non_qb if p.get("round_num") and p["round_num"] >= MIN_ROUND_FOR_STEAL and p["total_points"] is not None]
        steals = sorted(late, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

    else:  # auction
        valued = [p for p in non_qb if p["points_per_dollar"] is not None]
        best_value = sorted(valued, key=lambda p: p["points_per_dollar"], reverse=True)[:TOP_N]

        expensive = [p for p in non_qb if cheap_cutoff is not None and p.get("bid_amount") and p["bid_amount"] >= expensive_cutoff and p["total_points"] is not None]
        busts = sorted(expensive, key=lambda p: p["total_points"])[:TOP_N]
        stars = sorted(expensive, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

        cheap = [p for p in non_qb if cheap_cutoff is not None and p.get("bid_amount") and p["bid_amount"] <= cheap_cutoff and p["total_points"] is not None]
        steals = sorted(cheap, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

    return {
        "best_value_picks": best_value,
        "best_steals": steals,
        "stars": stars,
        "biggest_busts": busts,
        "total_picks_this_era": len([p for p in picks if p["draft_type"] == era]),
        "complete_picks_this_era": len(complete),
    }


def build_manager_profiles(pick_records, cheap_cutoff, expensive_cutoff):
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

        has_snake = any(p["draft_type"] == "snake" for p in picks)
        has_auction = any(p["draft_type"] == "auction" for p in picks)

        eras = {}
        if has_snake:
            eras["snake"] = build_era_categories(picks, "snake", cheap_cutoff, expensive_cutoff)
        if has_auction:
            eras["auction"] = build_era_categories(picks, "auction", cheap_cutoff, expensive_cutoff)

        # Captain at the Helm: QB-only, raw total_points, UNCHANGED across
        # eras - round/price bias doesn't apply to a raw-points ranking.
        qb_picks = [p for p in complete_picks if p["position"] == QB_POSITION and p["total_points"] is not None]
        captain_at_the_helm = sorted(qb_picks, key=lambda p: p["total_points"], reverse=True)[:TOP_N]

        # Signature picks: unaffected by era - repeat-drafting is a loyalty
        # signal regardless of draft format.
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
            "has_snake_era": has_snake,
            "has_auction_era": has_auction,
            "eras": eras,
            "captain_at_the_helm": captain_at_the_helm,
            "signature_picks": signature,
        }

    return profiles


# ---------------------------------------------------------------------------
# League-wide leaders
# ---------------------------------------------------------------------------

def build_league_leaders(profiles, pick_records, cheap_cutoff, expensive_cutoff):
    with_retention = [p for p in profiles.values() if p["retention_rate"] is not None]

    def top_by(items, key, reverse=True, n=3):
        return sorted(items, key=lambda x: x[key], reverse=reverse)[:n]

    most_loyal = top_by(with_retention, "retention_rate", reverse=True)
    biggest_churner = top_by(with_retention, "retention_rate", reverse=False)

    # Era-split league-wide best/worst picks - NOT comparable across eras
    snake_complete = [r for r in pick_records if r["data_complete"] and r["draft_type"] == "snake" and r["position"] != QB_POSITION]
    auction_complete = [r for r in pick_records if r["data_complete"] and r["draft_type"] == "auction" and r["position"] != QB_POSITION]

    snake_valued = [r for r in snake_complete if r["value_score"] is not None]
    best_pick_snake = sorted(snake_valued, key=lambda r: r["value_score"], reverse=True)[:TOP_N]
    snake_early = [r for r in snake_complete if r.get("round_num") and r["round_num"] <= MIN_ROUND_FOR_BUST]
    worst_bust_snake = sorted(snake_early, key=lambda r: r["total_points"])[:TOP_N]

    auction_valued = [r for r in auction_complete if r["points_per_dollar"] is not None]
    best_pick_auction = sorted(auction_valued, key=lambda r: r["points_per_dollar"], reverse=True)[:TOP_N]
    auction_expensive = [r for r in auction_complete if cheap_cutoff is not None and r.get("bid_amount") and r["bid_amount"] >= expensive_cutoff]
    worst_bust_auction = sorted(auction_expensive, key=lambda r: r["total_points"])[:TOP_N]

    qb_complete = [r for r in pick_records if r["data_complete"] and r["position"] == QB_POSITION and r["total_points"] is not None]
    best_qb_campaign_ever = sorted(qb_complete, key=lambda r: r["total_points"], reverse=True)[:TOP_N]

    # NEW auction-only categories, no snake equivalent:
    all_auction_bids = [r for r in pick_records if r["draft_type"] == "auction" and r.get("bid_amount") and r["data_complete"]]
    highest_single_bid_ever = sorted(all_auction_bids, key=lambda r: r["bid_amount"], reverse=True)[:TOP_N]

    # Career auction efficiency: aggregate points/dollar across EVERY
    # auction pick a manager has ever made, not just their top highlight.
    manager_auction_totals = defaultdict(lambda: {"points": 0.0, "spent": 0, "name": None})
    for r in pick_records:
        if r["draft_type"] == "auction" and r["data_complete"] and r["position"] != QB_POSITION and r.get("bid_amount"):
            entry = manager_auction_totals[r["drafted_by_canonical_id"]]
            entry["points"] += r["total_points"] or 0
            entry["spent"] += r["bid_amount"]
            entry["name"] = r["drafted_by_name"]

    career_efficiency = []
    for cid, data in manager_auction_totals.items():
        if data["spent"] > 0:
            career_efficiency.append({
                "owner_name": data["name"],
                "total_points": round(data["points"], 2),
                "total_spent": data["spent"],
                "points_per_dollar": round(data["points"] / data["spent"], 3),
            })
    best_career_auction_efficiency = sorted(career_efficiency, key=lambda x: x["points_per_dollar"], reverse=True)[:TOP_N]

    return {
        "most_loyal_managers": most_loyal,
        "biggest_roster_churners": biggest_churner,
        "best_picks_snake_era": best_pick_snake,
        "worst_busts_snake_era": worst_bust_snake,
        "best_picks_auction_era": best_pick_auction,
        "worst_busts_auction_era": worst_bust_auction,
        "best_qb_campaigns_in_league_history": best_qb_campaign_ever,
        "highest_single_bid_ever": highest_single_bid_ever,
        "best_career_auction_efficiency": best_career_auction_efficiency,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()
    draft_types = load_draft_types()

    pick_records = build_pick_records(history, id_to_canonical, canonical_owners, exclusions, draft_types)
    cheap_cutoff, expensive_cutoff = compute_bid_thresholds(pick_records)
    rarity_thresholds = compute_rarity_thresholds(pick_records)

    profiles = build_manager_profiles(pick_records, cheap_cutoff, expensive_cutoff)
    leaders = build_league_leaders(profiles, pick_records, cheap_cutoff, expensive_cutoff)

    incomplete_count = sum(1 for r in pick_records if not r["data_complete"])

    output = {
        "manager_profiles": profiles,
        "league_leaders": leaders,
        "notes": {
            "picks_with_no_recoverable_landing_spot": incomplete_count,
            "explanation": "These players were drafted, dropped, and never picked up by anyone by season's end - no point total OR POSITION is recoverable for them.",
            "value_score_formula": "SNAKE ERA: total_points * round_num. AUCTION ERA: total_points / bid_amount (points-per-dollar).",
            "qb_exclusion_note": "QBs are excluded from all value/steal/star/bust categories in BOTH eras - the round/price bias applies to either system. QBs get their own 'captain_at_the_helm' category instead, ranked by raw total_points, unchanged across eras.",
            "auction_thresholds": {
                "cheap_bid_cutoff": cheap_cutoff,
                "expensive_bid_cutoff": expensive_cutoff,
                "method": "25th/75th percentile of all real auction bid_amounts, computed fresh each run - not hardcoded.",
            },
            "rarity_thresholds": rarity_thresholds,
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(profiles)} manager profiles to {OUTPUT_PATH}")
    print(f"Cheap bid cutoff: ${cheap_cutoff} | Expensive bid cutoff: ${expensive_cutoff}")
    print(f"({incomplete_count} picks had no recoverable landing spot)")


if __name__ == "__main__":
    main()

