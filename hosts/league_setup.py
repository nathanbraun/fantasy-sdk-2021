import hosts.fleaflicker as site
from hosts.db import overwrite_league
from pandas import DataFrame
import sqlite3
import pandas as pd
from utilities import DB_PATH, ESPN_S2, SWID

LEAGUE_ID = 316893
TEAM_ID = 1605156

LEAGUE_NAME = "Family League"
HOST = 'fleaflicker'
SCORING = {'qb': 'pass4', 'skill': 'ppr0', 'dst': 'mfl'}

# open up our database connection
conn = sqlite3.connect(DB_PATH)

# team list
teams = site.get_teams_in_league(LEAGUE_ID)
overwrite_league(teams, 'teams', conn, LEAGUE_ID)

# schedule info
schedule = site.get_league_schedule(LEAGUE_ID)
overwrite_league(schedule, 'schedule', conn, LEAGUE_ID)

# league info
league = DataFrame([{'league_id': LEAGUE_ID, 'team_id': TEAM_ID, 'host':
                     HOST.lower(), 'name': LEAGUE_NAME, 'qb_scoring':
                     SCORING['qb'], 'skill_scoring': SCORING['skill'],
                     'dst_scoring': SCORING['dst']}])
overwrite_league(league, 'league', conn, LEAGUE_ID)
