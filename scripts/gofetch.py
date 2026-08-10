# SCRIPT TO FETCH LEAGUE DATA THROUGH ESPN API

# Imports

from dotenv import load_dotenv
import os
import json
from datetime import datetime
from espn_api.football import League

# Setup

load_dotenv()

LEAGUE_ID = int(os.getenv("LEAGUE_ID"))
ESPN_S2 = os.getenv("ESPN_S2")
SWID = os.getenv("ESPN_SWID")

# Update this manually once a year, after the season's final week has been played
CURRENT_YEAR = 2025

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "league_history.json")

# Helper functions: convert espn_api objects -> plain JSON-serializable dicts

def get_owner_id(team):
    """Stable identifier across years, tied to the ESPN account, not the team name."""
    if team.owners:
        return team.owners[0].get("id")
    return None


def get_owner_name(team):
    if team.owners:
        o = team.owners[0]
        name = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        return name if name else team.team_name
    return team.team_name


def roster_to_list(team):
    roster = getattr(team, "roster", None) or []
    out = []
    for p in roster:
        out.append({
            "player_id": getattr(p, "playerId", None),
            "player_name": getattr(p, "name", None),
            "position": getattr(p, "position", None),
            "pro_team": getattr(p, "proTeam", None),
            "total_points": getattr(p, "total_points", None),
            "avg_points": getattr(p, "avg_points", None),
        })
    return out


def team_to_dict(team):
    return {
        "team_id": team.team_id,
        "team_name": team.team_name,
        "team_abbrev": getattr(team, "team_abbrev", None),
        "owner_id": get_owner_id(team),
        "owner_name": get_owner_name(team),
        "wins": team.wins,
        "losses": team.losses,
        "ties": team.ties,
        "standing": team.standing,
        "final_standing": team.final_standing,
        "points_for": team.points_for,
        "points_against": team.points_against,
        "streak_type": getattr(team, "streak_type", None),
        "streak_length": getattr(team, "streak_length", None),
        "schedule_opponent_ids": [
            opp.team_id for opp in team.schedule
        ] if team.schedule else [],
        "scores": list(team.scores) if team.scores else [],
        "outcomes": list(team.outcomes) if team.outcomes else [],
        "final_roster": roster_to_list(team),
        "trades": getattr(team, "trades", None),
        "acquisitions": getattr(team, "acquisitions", None),
        "drops": getattr(team, "drops", None),
    }


def pick_to_dict(pick):
    return {
        "team_id": pick.team.team_id if pick.team else None,
        "owner_id": get_owner_id(pick.team) if pick.team else None,
        "player_id": pick.playerId,
        "player_name": pick.playerName,
        "round_num": pick.round_num,
        "round_pick": pick.round_pick,
        "bid_amount": getattr(pick, "bid_amount", None),
        "keeper_status": getattr(pick, "keeper_status", None),
    }


def matchup_to_dict(matchup):
    home_team = getattr(matchup, "home_team", None)
    away_team = getattr(matchup, "away_team", None)

    home_id = home_team.team_id if home_team else None
    away_id = away_team.team_id if away_team else None
    home_owner = get_owner_id(home_team) if home_team else None
    away_owner = get_owner_id(away_team) if away_team else None

    return {
        "home_team_id": home_id,
        "home_owner_id": home_owner,
        "home_score": getattr(matchup, "home_score", None),
        "away_team_id": away_id,
        "away_owner_id": away_owner,
        "away_score": getattr(matchup, "away_score", None),
        "is_playoff": getattr(matchup, "is_playoff", False),
        "matchup_type": getattr(matchup, "matchup_type", None),
        "is_bye": away_team is None or home_team is None,
    }


def settings_to_dict(settings):
    return {
        "name": getattr(settings, "name", None),
        "team_count": getattr(settings, "team_count", None),
        "reg_season_count": getattr(settings, "reg_season_count", None),
        "playoff_team_count": getattr(settings, "playoff_team_count", None),
        "veto_votes_required": getattr(settings, "veto_votes_required", None),
        "keeper_count": getattr(settings, "keeper_count", None),
    }


# Per-year pull: everything for a single season

def pull_season(year):
    print(f"Pulling {year}...")
    league = League(
        league_id=LEAGUE_ID,
        year=year,
        espn_s2=ESPN_S2,
        swid=SWID,
    )

    teams = [team_to_dict(t) for t in league.teams]
    draft = [pick_to_dict(p) for p in league.draft]
    settings = settings_to_dict(league.settings)

    matchups = {}
    max_week = 18  # safe upper bound; unplayed/nonexistent weeks are skipped below
    for week in range(1, max_week + 1):
        try:
            week_matchups = league.scoreboard(week=week)
        except Exception:
            continue

        parsed = []
        for m in week_matchups:
            home_score = getattr(m, "home_score", None)
            away_score = getattr(m, "away_score", None)
            if not home_score and not away_score:
                continue
            parsed.append(matchup_to_dict(m))

        if parsed:
            matchups[str(week)] = parsed

    return {
        "settings": settings,
        "teams": teams,
        "draft": draft,
        "matchups": matchups,
    }


# Main: bootstrap year range, loop, write JSON

def main():
    bootstrap = League(
        league_id=LEAGUE_ID,
        year=CURRENT_YEAR,
        espn_s2=ESPN_S2,
        swid=SWID,
    )
    all_years = bootstrap.previousSeasons + [bootstrap.year]
    print(f"Found {len(all_years)} seasons: {all_years}")

    full_history = {
        "pulled_at": datetime.now().isoformat(),
        "league_id": LEAGUE_ID,
        "seasons": {},
    }

    for year in all_years:
        full_history["seasons"][str(year)] = pull_season(year)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(full_history, f, indent=2)

    print(f"Done. Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

# End fetch script
