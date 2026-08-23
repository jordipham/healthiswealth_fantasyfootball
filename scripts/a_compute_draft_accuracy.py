"""
a_compute_draft_accuracy.py

Reads data/league_history.json, produces
data/raw_analytics/draft_accuracy.json.

ANALYSIS: does a team's PRESEASON projected roster strength (summed
across just the players they actually DRAFTED, not their full
end-of-season roster) correlate with their actual final standing?

SCOPING DECISION (confirmed against real data before building): a
team's final_roster includes players added via trades/waivers
throughout the season, NOT just draft picks - e.g. one real team had
20 players on their final roster but only drafted 16 of them. Summing
the full final_roster would conflate DRAFT skill with IN-SEASON
roster management skill, which are different things. This analysis
scopes strictly to players actually drafted by that team that year.

projected_total_points is only available on a player's final_roster
entry (wherever they ultimately landed, possibly a DIFFERENT team than
who drafted them) - so a cross-team lookup is built first, same
pattern as compute_draft_day_profiler.py's build_final_landing_spots().

KNOWN LIMITATION (same one documented elsewhere): a player drafted,
dropped, and never reclaimed by ANYONE has no recoverable projection
either, since it only exists on final_roster entries. This means
"total projected points" is a slight undercount for teams with many
picks that vanished entirely - noted directly in the output.

No draft-type (snake/auction) distinction needed here - summing raw
projections doesn't depend on what a pick cost or which round it was.

CORRELATION: hand-rolled Spearman rank correlation (no scipy) between
[rank by total projected points] and [rank by actual final_standing],
computed BOTH per-season (small n, ~8-14 teams) AND pooled across all
team-seasons combined (~94 data points, more statistically meaningful).

Run with: python a_compute_draft_accuracy.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OVERRIDES_PATH = os.path.join(SCRIPT_DIR, "co_owner_overrides.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "raw_analytics", "draft_accuracy.json")


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
# Cross-team projection lookup (projections live on final_roster,
# regardless of who ends up owning the player)
# ---------------------------------------------------------------------------

def build_projection_lookup(season_data):
    lookup = {}
    for team in season_data.get("teams", []):
        for p in team.get("final_roster", []) or []:
            pid = p.get("player_id")
            proj = p.get("projected_total_points")
            if pid is not None and proj is not None:
                lookup[pid] = proj
    return lookup


# ---------------------------------------------------------------------------
# Hand-rolled Spearman rank correlation (no scipy)
# ---------------------------------------------------------------------------

def rank_values(values):
    """Returns a list of ranks (1 = highest value) matching input order.
    Assumes no ties, which is safe here given continuous float sums."""
    sorted_indices = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    ranks = [0] * len(values)
    for rank, idx in enumerate(sorted_indices, start=1):
        ranks[idx] = rank
    return ranks


def spearman_correlation(x_values, y_values):
    n = len(x_values)
    if n < 2:
        return None
    x_ranks = rank_values(x_values)
    y_ranks = rank_values(y_values)
    d_squared_sum = sum((x_ranks[i] - y_ranks[i]) ** 2 for i in range(n))
    rho = 1 - (6 * d_squared_sum) / (n * (n ** 2 - 1))
    return round(rho, 4)


# ---------------------------------------------------------------------------
# Per-season computation
# ---------------------------------------------------------------------------

def compute_season(season_data, year, id_to_canonical, canonical_owners, exclusions):
    projection_lookup = build_projection_lookup(season_data)
    teams_by_id = {t["team_id"]: t for t in season_data.get("teams", [])}

    # Sum projected points for players actually DRAFTED by each team
    drafted_by_team = {}
    picks_with_known_projection = {}
    total_picks_by_team = {}
    for pick in season_data.get("draft", []):
        tid = pick.get("team_id")
        pid = pick.get("player_id")
        total_picks_by_team[tid] = total_picks_by_team.get(tid, 0) + 1
        proj = projection_lookup.get(pid)
        if proj is not None:
            drafted_by_team[tid] = drafted_by_team.get(tid, 0.0) + proj
            picks_with_known_projection[tid] = picks_with_known_projection.get(tid, 0) + 1

    team_rows = []
    for tid, team in teams_by_id.items():
        if tid not in drafted_by_team:
            continue  # no recoverable projection data for any of this team's picks
        credited = resolve_credited_owners(team, year, id_to_canonical, canonical_owners, exclusions)
        for cid, name in credited:
            if cid is None:
                continue
            team_rows.append({
                "canonical_id": cid,
                "owner_name": name,
                "total_projected_points": round(drafted_by_team[tid], 2),
                "final_standing": team.get("final_standing"),
                "picks_with_known_projection": picks_with_known_projection.get(tid, 0),
                "total_picks": total_picks_by_team.get(tid, 0),
            })

    if len(team_rows) < 2:
        return None, team_rows

    correlation = spearman_correlation(
        [r["total_projected_points"] for r in team_rows],
        [-r["final_standing"] for r in team_rows],  # negate: higher projection SHOULD correspond to BETTER (lower-numbered) finish
    )

    return correlation, team_rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()
    exclusions = load_exclusions()

    seasons_output = {}
    all_team_rows = []

    for year, season_data in history.get("seasons", {}).items():
        correlation, team_rows = compute_season(season_data, int(year), id_to_canonical, canonical_owners, exclusions)
        seasons_output[year] = {
            "spearman_correlation": correlation,
            "teams": team_rows,
        }
        all_team_rows.extend(team_rows)

    # Pooled correlation across ALL team-seasons combined (~94 data points, more statistically meaningful than any single season)
    overall_correlation = spearman_correlation(
        [r["total_projected_points"] for r in all_team_rows],
        [-r["final_standing"] for r in all_team_rows],
    )

    output = {
        "seasons": seasons_output,
        "overall": {
            "spearman_correlation": overall_correlation,
            "total_team_seasons": len(all_team_rows),
        },
        "notes": {
            "scope": "Only players actually DRAFTED by a team are summed (not their full end-of-season roster) - a team's final roster includes waiver/trade additions, which would conflate draft skill with in-season roster management.",
            "correlation_method": "Hand-computed Spearman rank correlation (no scipy). Compares [rank by total projected points] against [rank by actual final_standing]. A correlation near +1.0 means projections strongly predicted outcomes; near 0 means projections had little predictive power; negative would mean projections were actually inversely related to outcomes.",
            "known_limitation": "Players drafted, dropped, and never reclaimed by anyone have no recoverable projection (same limitation as Draft Day Profiler) - team totals are a slight undercount for rosters with many such picks. picks_with_known_projection / total_picks is included per team so this gap is visible, not hidden.",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote draft accuracy for {len(seasons_output)} seasons, {len(all_team_rows)} team-seasons pooled")
    print(f"Overall pooled Spearman correlation: {overall_correlation}")


if __name__ == "__main__":
    main()
