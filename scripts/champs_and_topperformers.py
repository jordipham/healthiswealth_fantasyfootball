import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "hall_of_champions.json")

TOP_N = 3  # how many top performers to include per champion


def get_champion(season_data):
    """Find the team with final_standing == 1 for this season."""
    for team in season_data.get("teams", []):
        if team.get("final_standing") == 1:
            return team
    return None


def get_top_performers(team, n=TOP_N):
    """
    Rank a team's final_roster by total_points, descending.
    Defensive against missing/None total_points (shouldn't happen post-fix,
    but a bad or partial pull is still possible).
    """
    roster = team.get("final_roster", []) or []
    valid = [p for p in roster if p.get("total_points") is not None]
    ranked = sorted(valid, key=lambda p: p["total_points"], reverse=True)
    return ranked[:n]


def build_hall_of_champions(history):
    seasons = history.get("seasons", {})
    hall = []

    for year in sorted(seasons.keys(), key=int):
        season_data = seasons[year]
        champion = get_champion(season_data)

        if champion is None:
            print(f"WARNING: no champion found for {year} (final_standing==1 missing) - skipping")
            continue

        top_performers = get_top_performers(champion)

        hall.append({
            "year": int(year),
            "owner_id": champion.get("owner_id"),
            "owner_name": champion.get("owner_name"),
            "team_name": champion.get("team_name"),
            "record": f"{champion.get('wins')}-{champion.get('losses')}-{champion.get('ties')}",
            "points_for": champion.get("points_for"),
            "points_against": champion.get("points_against"),
            "top_performers": [
                {
                    "player_name": p.get("player_name"),
                    "position": p.get("position"),
                    "pro_team": p.get("pro_team"),
                    "total_points": p.get("total_points"),
                    "avg_points": p.get("avg_points"),
                }
                for p in top_performers
            ],
        })

    return hall


def main():
    with open(INPUT_PATH) as f:
        history = json.load(f)

    hall = build_hall_of_champions(history)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(hall, f, indent=2)

    print(f"Wrote {len(hall)} seasons to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
