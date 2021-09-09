import sqlite3
from pandas import DataFrame, Series
import pandas as pd
import hosts.fleaflicker as site
from utilities import DB_PATH

LEAGUE_ID = 316893
TEAM_ID = 1605156

teams = site.get_teams_in_league(LEAGUE_ID)
schedule = site.get_league_schedule(LEAGUE_ID)

# conn
conn = sqlite3.connect(DB_PATH)

# brute force replace option
teams = site.get_teams_in_league(LEAGUE_ID)

teams.to_sql('teams', conn, index=False, if_exists='replace')

# delete existing teams data for that league, then append
from textwrap import dedent

conn.execute(dedent(f"""
    DELETE FROM teams
    WHERE league_id = {LEAGUE_ID};"""))
teams.to_sql('teams', conn, index=False, if_exists='append')

def clear_league_from_table1(league_id, table, conn):
    conn.execute(dedent(f"""
        DELETE FROM {table}
        WHERE league_id = {league_id};"""))

clear_league_from_table1(LEAGUE_ID, 'teams', conn)
teams.to_sql('teams', conn, index=False, if_exists='append')

# delete existing teams data for that league, then append
clear_league_from_table1(LEAGUE_ID, 'schedule', conn)

def clear_league_from_table2(league_id, table, conn):
    tables_in_db = [x[0] for x in list(conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"))]

    if table in tables_in_db:
        conn.execute(dedent(f"""
            DELETE FROM {table}
            WHERE league_id = {league_id};"""))

clear_league_from_table2(LEAGUE_ID, 'schedule', conn)
schedule.to_sql('schedule', conn, index=False, if_exists='append')

def overwrite_league(df, name, conn, league_id):
    clear_league_from_table2(league_id, name, conn)
    df.to_sql(name, conn, index=False, if_exists='append')

overwrite_league(schedule, 'schedule', conn, LEAGUE_ID)

clear_league_from_table2(LEAGUE_ID, 'schedule', conn)
schedule.to_sql('schedule', conn, index=False, if_exists='append')

def read_league(name, league_id, conn):
    return pd.read_sql(dedent(
        f"""
        SELECT *
        FROM {name}
        WHERE league_id = {league_id}
        """), conn)

read_league('teams', LEAGUE_ID, conn)

league = DataFrame([{'league_id': LEAGUE_ID, 'team_id': TEAM_ID,
                    'host': 'fleaflicker', 'name': 'Family League'}])

overwrite_league(league, 'league', conn, LEAGUE_ID)
