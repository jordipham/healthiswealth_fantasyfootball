# SCRIPT TO FETCH LEAGUE DATA THROUGH ESPN API

# imports
from espn_api.football import League
from dotenv import load_dotenv
import os

# access keys
load_dotenv()
# LEAGUE_ID = os.getenv("LEAGUE_ID")
ESPN_S2 = os.getenv("ESPN_S2")
ESPN_SWID = os.getenv("ESPN_SWID")

# check keys
# print(LEAGUE_ID)
# print(ESPN_S2)
# print(ESPN_SWID)


# end fetch script