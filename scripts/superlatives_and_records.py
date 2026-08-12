"""
compute_superlatives.py

Reads data/league_history.json + owner_map.json, produces
data/derived/superlatives.json - single-season records and
all-time career records across the whole league history.

Co-ownership handling: any team with multiple owners (see
team["all_owners"]) credits EVERY co-owner fully for that team's
stats that season - both in season records (e.g. if a co-owned team
holds the highest points_for, both owners appear as tied leaders)
and in career records (each co-owner's career totals include that
season's full wins/losses/points/trades/championship, etc).

Pure read/compute/write - no ESPN API calls.

Run with: python compute_superlatives.py
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "superlatives.json")


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


def resolve_owner(owner_id, id_to_canonical, canonical_owners):
    canonical_id = id_to_canonical.get(owner_id)
    if canonical_id is None:
        return None, f"UNKNOWN ({owner_id})"
    return canonical_id, canonical_owners[canonical_id]["display_name"]


def resolve_all_owners(team, id_to_canonical, canonical_owners):
    """
    Returns [(canonical_id, display_name), ...] for every owner on this
    team - primary plus any co-owners. Falls back to the single primary
    owner if all_owners isn't present (older raw pulls).
    """
    all_owners = team.get("all_owners") or []
    if not all_owners:
        oid = team.get("owner_id")
        cid, name = resolve_owner(oid, id_to_canonical, canonical_owners)
        return [(cid, name)]

    resolved = []
    for o in all_owners:
        cid, name = resolve_owner(o.get("id"), id_to_canonical, canonical_owners)
        resolved.append((cid, name))
    return resolved


# ---------------------------------------------------------------------------
# Single-season records
# ---------------------------------------------------------------------------

def compute_season_records(history, id_to_canonical, canonical_owners):
    records = {
        "highest_points_for": [],
        "lowest_points_for": [],
        "highest_points_against": [],
        "lowest_points_against": [],
        "best_record": [],
        "worst_record": [],
        "longest_win_streak": [],
        "longest_losing_streak": [],
        "most_trades_season": [],
        "most_acquisitions_season": [],
        "highest_single_week_score": [],
        "lowest_single_week_score": [],
        "biggest_blowout": [],
        "closest_game": [],
    }

    def better(current_list, candidate, key, higher_is_better=True):
        """
        current_list is a list of tied leaders (or empty). Extends it if
        candidate ties the current best, replaces it if candidate beats
        the current best, leaves it unchanged if candidate is worse.
        """
        if not current_list:
            return [candidate]
        current_value = current_list[0][key]
        if candidate[key] == current_value:
            return current_list + [candidate]
        is_better = candidate[key] > current_value if higher_is_better else candidate[key] < current_value
        return [candidate] if is_better else current_list

    for year, season_data in history.get("seasons", {}).items():
        teams_by_id = {t.get("team_id"): t for t in season_data.get("teams", [])}

        for team in season_data.get("teams", []):
            owners = resolve_all_owners(team, id_to_canonical, canonical_owners)
            games = (team.get("wins", 0) or 0) + (team.get("losses", 0) or 0) + (team.get("ties", 0) or 0)
            win_pct = (team.get("wins", 0) or 0) / games if games else 0

            # One candidate per co-owner - if the team holds the record,
            # every co-owner gets credited (and tie logic in better()
            # naturally keeps them together).
            is_co_owned = len(owners) > 1
            for _, owner_name in owners:
                base = {
                    "year": int(year),
                    "owner_name": owner_name,
                    "team_name": team.get("team_name"),
                    "co_owned": is_co_owned,
                }

                if team.get("points_for") is not None:
                    c = {**base, "value": team["points_for"]}
                    records["highest_points_for"] = better(records["highest_points_for"], c, "value", True)
                    records["lowest_points_for"] = better(records["lowest_points_for"], c, "value", False)

                if team.get("points_against") is not None:
                    c = {**base, "value": team["points_against"]}
                    records["highest_points_against"] = better(records["highest_points_against"], c, "value", True)
                    records["lowest_points_against"] = better(records["lowest_points_against"], c, "value", False)

                if games:
                    c = {**base, "value": win_pct, "record": f"{team.get('wins')}-{team.get('losses')}-{team.get('ties')}"}
                    records["best_record"] = better(records["best_record"], c, "value", True)
                    records["worst_record"] = better(records["worst_record"], c, "value", False)

                if team.get("streak_type") == "WIN" and team.get("streak_length"):
                    c = {**base, "value": team["streak_length"]}
                    records["longest_win_streak"] = better(records["longest_win_streak"], c, "value", True)

                if team.get("streak_type") == "LOSS" and team.get("streak_length"):
                    c = {**base, "value": team["streak_length"]}
                    records["longest_losing_streak"] = better(records["longest_losing_streak"], c, "value", True)

                if team.get("trades") is not None:
                    c = {**base, "value": team["trades"]}
                    records["most_trades_season"] = better(records["most_trades_season"], c, "value", True)

                if team.get("acquisitions") is not None:
                    c = {**base, "value": team["acquisitions"]}
                    records["most_acquisitions_season"] = better(records["most_acquisitions_season"], c, "value", True)

        # Weekly score + margin records, joined via team_id (not the
        # singular home_owner_id/away_owner_id) so co-owners are caught.
        for week, matchups in season_data.get("matchups", {}).items():
            for m in matchups:
                if m.get("is_bye"):
                    continue

                home_score = m.get("home_score")
                away_score = m.get("away_score")
                home_team = teams_by_id.get(m.get("home_team_id"))
                away_team = teams_by_id.get(m.get("away_team_id"))

                home_owners = resolve_all_owners(home_team, id_to_canonical, canonical_owners) if home_team else []
                away_owners = resolve_all_owners(away_team, id_to_canonical, canonical_owners) if away_team else []

                if home_score is not None:
                    home_is_co = len(home_owners) > 1
                    for _, home_name in home_owners:
                        c = {"year": int(year), "week": int(week), "owner_name": home_name, "value": home_score, "co_owned": home_is_co}
                        records["highest_single_week_score"] = better(records["highest_single_week_score"], c, "value", True)
                        records["lowest_single_week_score"] = better(records["lowest_single_week_score"], c, "value", False)

                if away_score is not None:
                    away_is_co = len(away_owners) > 1
                    for _, away_name in away_owners:
                        c = {"year": int(year), "week": int(week), "owner_name": away_name, "value": away_score, "co_owned": away_is_co}
                        records["highest_single_week_score"] = better(records["highest_single_week_score"], c, "value", True)
                        records["lowest_single_week_score"] = better(records["lowest_single_week_score"], c, "value", False)

                if home_score is not None and away_score is not None:
                    margin = abs(home_score - away_score)
                    home_display = " & ".join(n for _, n in home_owners) if home_owners else "UNKNOWN"
                    away_display = " & ".join(n for _, n in away_owners) if away_owners else "UNKNOWN"
                    c = {
                        "year": int(year), "week": int(week),
                        "matchup": f"{home_display} ({home_score}) vs {away_display} ({away_score})",
                        "value": margin,
                        "home_co_owned": len(home_owners) > 1,
                        "away_co_owned": len(away_owners) > 1,
                    }
                    records["biggest_blowout"] = better(records["biggest_blowout"], c, "value", True)
                    records["closest_game"] = better(records["closest_game"], c, "value", False)

    return records


# ---------------------------------------------------------------------------
# Career / all-time records
# ---------------------------------------------------------------------------

def compute_career_records(history, id_to_canonical, canonical_owners):
    careers = {}

    def get_career(canonical_id, name):
        if canonical_id not in careers:
            careers[canonical_id] = {
                "owner_name": name,
                "championships": 0,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "trades": 0,
                "acquisitions": 0,
                "last_place_finishes": 0,
                "years_played": [],
                "co_ownership_history": [],  # [{"year": 2020, "co_owners": ["Saurab Nooguri"]}, ...]
                "last_championship_year": None,
            }
        return careers[canonical_id]

    for year, season_data in history.get("seasons", {}).items():
        teams = season_data.get("teams", [])
        max_standing = max((t.get("final_standing") or 0) for t in teams) if teams else 0

        for team in teams:
            owners = resolve_all_owners(team, id_to_canonical, canonical_owners)
            is_co_owned = len(owners) > 1

            # Every co-owner on this team gets full credit for the season.
            for canonical_id, name in owners:
                if canonical_id is None:
                    continue  # unmapped owner - run check_unmapped_owners.py

                c = get_career(canonical_id, name)
                c["wins"] += team.get("wins", 0) or 0
                c["losses"] += team.get("losses", 0) or 0
                c["ties"] += team.get("ties", 0) or 0
                c["trades"] += team.get("trades", 0) or 0
                c["acquisitions"] += team.get("acquisitions", 0) or 0
                c["years_played"].append(int(year))

                if is_co_owned:
                    # Everyone else on this team that year, excluding self
                    co_owner_names = [n for cid, n in owners if cid != canonical_id]
                    c["co_ownership_history"].append({
                        "year": int(year),
                        "co_owners": co_owner_names,
                    })

                if team.get("final_standing") == 1:
                    c["championships"] += 1
                    if c["last_championship_year"] is None or int(year) > c["last_championship_year"]:
                        c["last_championship_year"] = int(year)

                if team.get("final_standing") == max_standing and max_standing > 0:
                    c["last_place_finishes"] += 1

    current_year = max((int(y) for y in history.get("seasons", {}).keys()), default=None)

    for canonical_id, c in careers.items():
        games = c["wins"] + c["losses"] + c["ties"]
        c["win_pct"] = round(c["wins"] / games, 4) if games else None
        c["years_played"] = sorted(set(c["years_played"]))
        c["co_ownership_history"] = sorted(c["co_ownership_history"], key=lambda x: x["year"])

        if c["championships"] == 0:
            c["championship_drought"] = "never won"
        else:
            c["championship_drought"] = current_year - c["last_championship_year"]

    def get_leaders(careers_dict, key, reverse=True):
        valid = [c for c in careers_dict.values() if c.get(key) is not None]
        if not valid:
            return []
        best_value = max((c[key] for c in valid)) if reverse else min((c[key] for c in valid))
        return [c for c in valid if c[key] == best_value]

    most_championships = get_leaders(careers, "championships", reverse=True)
    best_win_pct = get_leaders(careers, "win_pct", reverse=True)
    worst_win_pct = get_leaders(careers, "win_pct", reverse=False)
    most_trades_career = get_leaders(careers, "trades", reverse=True)
    most_last_place = get_leaders(careers, "last_place_finishes", reverse=True)

    return {
        "all_managers": careers,
        "leaders": {
            "most_championships": most_championships,
            "best_career_win_pct": best_win_pct,
            "worst_career_win_pct": worst_win_pct,
            "most_trades_career": most_trades_career,
            "most_last_place_finishes": most_last_place,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(HISTORY_PATH) as f:
        history = json.load(f)

    canonical_owners, id_to_canonical = load_owner_map()

    season_records = compute_season_records(history, id_to_canonical, canonical_owners)
    career_records = compute_career_records(history, id_to_canonical, canonical_owners)

    output = {
        "season_records": season_records,
        "career_records": career_records,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

    