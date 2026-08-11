# SCRIPT COMPUTES SINGLE-SEASON SUPERLATIVES AND RECORDS FOR THE LEAGUE

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OWNER_MAP_PATH = os.path.join(SCRIPT_DIR, "owner_map.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "superlatives.json")

# Owner resolution

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


# Single-season records


def compute_season_records(history, id_to_canonical, canonical_owners):
    records = {
        "highest_points_for": None,
        "lowest_points_for": None,
        "highest_points_against": None,
        "lowest_points_against": None,
        "best_record": None,
        "worst_record": None,
        "longest_win_streak": None,
        "longest_losing_streak": None,
        "most_trades_season": None,
        "most_acquisitions_season": None,
        "highest_single_week_score": None,
        "lowest_single_week_score": None,
        "biggest_blowout": None,
        "closest_game": None,
    }

    def better(current, candidate, key, higher_is_better=True):
        if current is None:
            return candidate
        if higher_is_better:
            return candidate if candidate[key] > current[key] else current
        else:
            return candidate if candidate[key] < current[key] else current

    for year, season_data in history.get("seasons", {}).items():
        for team in season_data.get("teams", []):
            _, name = resolve_owner(team.get("owner_id"), id_to_canonical, canonical_owners)
            games = (team.get("wins", 0) or 0) + (team.get("losses", 0) or 0) + (team.get("ties", 0) or 0)
            win_pct = (team.get("wins", 0) or 0) / games if games else 0

            base = {
                "year": int(year),
                "owner_name": name,
                "team_name": team.get("team_name"),
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

        # Weekly score + margin records, from matchups
        for week, matchups in season_data.get("matchups", {}).items():
            for m in matchups:
                if m.get("is_bye"):
                    continue

                home_score = m.get("home_score")
                away_score = m.get("away_score")
                home_id = m.get("home_owner_id")
                away_id = m.get("away_owner_id")

                if home_score is not None:
                    _, home_name = resolve_owner(home_id, id_to_canonical, canonical_owners)
                    c = {"year": int(year), "week": int(week), "owner_name": home_name, "value": home_score}
                    records["highest_single_week_score"] = better(records["highest_single_week_score"], c, "value", True)
                    records["lowest_single_week_score"] = better(records["lowest_single_week_score"], c, "value", False)

                if away_score is not None:
                    _, away_name = resolve_owner(away_id, id_to_canonical, canonical_owners)
                    c = {"year": int(year), "week": int(week), "owner_name": away_name, "value": away_score}
                    records["highest_single_week_score"] = better(records["highest_single_week_score"], c, "value", True)
                    records["lowest_single_week_score"] = better(records["lowest_single_week_score"], c, "value", False)

                if home_score is not None and away_score is not None:
                    margin = abs(home_score - away_score)
                    _, home_name = resolve_owner(home_id, id_to_canonical, canonical_owners)
                    _, away_name = resolve_owner(away_id, id_to_canonical, canonical_owners)
                    c = {
                        "year": int(year), "week": int(week),
                        "matchup": f"{home_name} ({home_score}) vs {away_name} ({away_score})",
                        "value": margin,
                    }
                    records["biggest_blowout"] = better(records["biggest_blowout"], c, "value", True)
                    records["closest_game"] = better(records["closest_game"], c, "value", False)

    return records


# Career / all-time records


def compute_career_records(history, id_to_canonical, canonical_owners):
    careers = {}  # canonical_id -> aggregated stats

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
                "last_championship_year": None,
            }
        return careers[canonical_id]

    for year, season_data in history.get("seasons", {}).items():
        teams = season_data.get("teams", [])
        max_standing = max((t.get("final_standing") or 0) for t in teams) if teams else 0

        for team in teams:
            canonical_id, name = resolve_owner(team.get("owner_id"), id_to_canonical, canonical_owners)
            if canonical_id is None:
                continue  # unmapped owner - run check_unmapped_owners.py

            c = get_career(canonical_id, name)
            c["wins"] += team.get("wins", 0) or 0
            c["losses"] += team.get("losses", 0) or 0
            c["ties"] += team.get("ties", 0) or 0
            c["trades"] += team.get("trades", 0) or 0
            c["acquisitions"] += team.get("acquisitions", 0) or 0
            c["years_played"].append(int(year))

            if team.get("final_standing") == 1:
                c["championships"] += 1
                if c["last_championship_year"] is None or int(year) > c["last_championship_year"]:
                    c["last_championship_year"] = int(year)

            if team.get("final_standing") == max_standing and max_standing > 0:
                c["last_place_finishes"] += 1

    current_year = max((int(y) for y in history.get("seasons", {}).keys()), default=None)

    # Finalize: win %, championship drought
    for canonical_id, c in careers.items():
        games = c["wins"] + c["losses"] + c["ties"]
        c["win_pct"] = round(c["wins"] / games, 4) if games else None
        c["years_played"] = sorted(c["years_played"])

        if c["championships"] == 0:
            c["championship_drought"] = "never won"
        else:
            c["championship_drought"] = current_year - c["last_championship_year"]

    most_championships = max(careers.values(), key=lambda c: c["championships"], default=None)
    best_win_pct = max(
        (c for c in careers.values() if c["win_pct"] is not None),
        key=lambda c: c["win_pct"], default=None
    )
    worst_win_pct = min(
        (c for c in careers.values() if c["win_pct"] is not None),
        key=lambda c: c["win_pct"], default=None
    )
    most_trades_career = max(careers.values(), key=lambda c: c["trades"], default=None)
    most_last_place = max(careers.values(), key=lambda c: c["last_place_finishes"], default=None)

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


# Main


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

