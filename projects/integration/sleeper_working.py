import requests
import numpy as np
from pandas import DataFrame, Series
import pandas as pd
from utilities import LICENSE_KEY, generate_token, master_player_lookup

import json
pd.options.mode.chained_assignment = None

LEAGUE_ID = 717250053961510912
WEEK = 2

roster_url = f'https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters'
matchup_url = f'https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{WEEK}'

roster_json = requests.get(roster_url).json()
# matchup_json = requests.get(matchup_url).json()

with open('./projects/integration/raw/sleeper/matchup.json') as f:
    matchup_json = json.load(f)

team9 = matchup_json[9]
team9['starters']

settings_url = f'https://api.sleeper.app/v1/league/{LEAGUE_ID}'
settings_json = requests.get(settings_url).json()

positions = settings_json['roster_positions']

from utilities import (LICENSE_KEY, generate_token, master_player_lookup)
token = generate_token(LICENSE_KEY)['token']
fantasymath_players = master_player_lookup(token)

fantasymath_players.head()

starters9 = Series(team9['starters']).to_frame('sleeper_id')
starters9

DataFrame([{'sleeper_id': x} for x in team9['starters']])

DataFrame(team9['starters'], columns=['sleeper_id'])

starters9_w_info = pd.merge(starters9, fantasymath_players, how='left')
starters9_w_info

starters9_w_info['actual'] = team9['starters_points']
starters9_w_info

starters9_w_info.loc[starters9_w_info['actual'] == 0, 'actual'] = np.nan
starters9_w_info

starters9_w_info['team_position'] = [x for x in positions if x != 'BN']
starters9_w_info

wrs = starters9_w_info.query("team_position == 'WR'")

suffix = Series(range(1, len(wrs) + 1), index=wrs.index)

wrs['team_position'] + suffix.astype(str)

def add_pos_suffix(df_subset):
    if len(df_subset) > 1:
        suffix = Series(range(1, len(df_subset) + 1), index=df_subset.index)

        df_subset['team_position'] = df_subset['team_position'] + suffix.astype(str)
    return df_subset

starters9_pos = pd.concat([
    add_pos_suffix(starters9_w_info.query(f"team_position == '{x}'"))
    for x in starters9_w_info['team_position'].unique()])

players9 = Series(team9['players']).to_frame('sleeper_id')
players9_w_info = pd.merge(players9, fantasymath_players, how='left')

team9['players_points']

players9_w_info['actual'] = (
    players9_w_info['sleeper_id'].replace(team9['players_points']))

bench_players = set(team9['players']) - set(team9['starters'])

bench_df = players9_w_info.query(f"sleeper_id in {tuple(bench_players)}")
bench_df['team_position'] = 'BN'
bench_df.loc[bench_df['actual'] == 0, 'actual'] = np.nan
bench_df

team9_df = pd.concat([starters9_pos, bench_df], ignore_index=True)
team9_df.drop(['yahoo_id', 'espn_id', 'fleaflicker_id', 'sleeper_id'], axis=1,
              inplace=True)
team9_df.rename(columns={'position': 'player_position'}, inplace=True)
team9_df['start'] = team9_df['team_position'] != 'BN'
team9_df['name'] = team9_df['fantasymath_id'].str.replace('-', ' ').str.title()
team9_df['team_id'] = team9['roster_id']
team9_df

def get_team_roster(team, lookup):
    # starters
    starters = Series(team['starters']).to_frame('sleeper_id')

    starters_w_info = pd.merge(starters, lookup, how='left')
    starters_w_info['actual'] = team['starters_points']
    starters_w_info.loc[starters_w_info['actual'] == 0, 'actual'] = np.nan
    starters_w_info['team_position'] = [x for x in positions if x != 'BN']

    starters_pos = pd.concat([
        add_pos_suffix(starters_w_info.query(f"team_position == '{x}'"))
        for x in starters_w_info['team_position'].unique()])

    players = Series(team['players']).to_frame('sleeper_id')
    players_w_info = pd.merge(players, fantasymath_players, how='left')

    players_w_info['actual'] = (
        players_w_info['sleeper_id'].replace(team['players_points']))

    bench_players = set(team['players']) - set(team['starters'])

    bench_df = players_w_info.query(f"sleeper_id in {tuple(bench_players)}")
    bench_df['team_position'] = 'BN'
    bench_df.loc[bench_df['actual'] == 0, 'actual'] = np.nan

    team_df = pd.concat([starters_pos, bench_df], ignore_index=True)
    team_df.drop(['yahoo_id', 'espn_id', 'fleaflicker_id', 'sleeper_id'], axis=1,
                inplace=True)
    team_df.rename(columns={'position': 'player_position'}, inplace=True)
    team_df['start'] = team_df['team_position'] != 'BN'
    team_df['name'] = team_df['fantasymath_id'].str.replace('-', ' ').str.title()
    team_df['team_id'] = team['roster_id']
    return team_df

get_team_roster(matchup_json[0], fantasymath_players)

all_rosters = pd.concat([get_team_roster(x, fantasymath_players) for x in
                         matchup_json], ignore_index=True)

all_rosters.sample(10)

def get_league_rosters(lookup, league_id, week):
    matchup_url = f'https://api.sleeper.app/v1/league/{league_id}/matchups/{week}'
    matchup_json = requests.get(matchup_url).json()

    return pd.concat([get_team_roster(x, lookup) for x in
                      matchup_json], ignore_index=True)

league_rosters = get_league_rosters(fantasymath_players, LEAGUE_ID, 2)

# team info
teams_url = f'https://api.sleeper.app/v1/league/{LEAGUE_ID}/users'
teams_json = requests.get(teams_url).json()

with open('./projects/integration/raw/sleeper/teams.json', 'w') as f:
    json.dump(teams_json, f)

with open('./projects/integration/raw/sleeper/teams.json') as f:
    teams_json = json.load(f)

team0 = teams_json[0]

def proc_team1(team):
    dict_to_return = {}

    dict_to_return['owner_id'] = team['user_id']
    dict_to_return['owner_name'] = team['display_name']
    return dict_to_return

proc_team1(team0)

def proc_team2(team, team_id):
    dict_to_return = {}

    dict_to_return['owner_id'] = team['user_id']
    dict_to_return['owner_name'] = team['display_name']
    dict_to_return['team_id'] = team_id
    return dict_to_return

proc_team2(team0, 1)

for i, team in enumerate(teams_json, start=1):
    print(i)
    print(team['display_name'])

all_teams = DataFrame(
    [proc_team2(team, i) for i, team in enumerate(teams_json, start=1)])

def get_teams_in_league(league_id):
    teams_url = f'https://api.sleeper.app/v1/league/{league_id}/users'
    teams_json = requests.get(teams_url).json()

    all_teams = DataFrame(
        [proc_team2(team, i) for i, team in enumerate(teams_json, start=1)])
    all_teams['league_id'] = league_id
    return all_teams

league_teams = get_teams_in_league(LEAGUE_ID)
league_teams

# schedule
with open('./projects/integration/raw/sleeper/matchup.json') as f:
    matchup_json = json.load(f)

team0 = matchup_json[0]

def proc_team_schedule(team):
    dict_to_return = {}
    dict_to_return['team_id'] = team['roster_id']
    dict_to_return['game_id'] = team['matchup_id']
    return dict_to_return

proc_team_schedule(team0)

schedule_w2 = DataFrame([proc_team_schedule(team) for team in matchup_json])

schedule_w2_wide = pd.merge(
    schedule_w2.drop_duplicates('game_id', keep='first'),
    schedule_w2.drop_duplicates('game_id', keep='last'), on='game_id')

schedule_w2_wide.rename(
    columns={'team_id_x': 'team1_id', 'team_id_y': 'team2_id'}, inplace=True)

schedule_w2_wide['season'] = 2021
schedule_w2_wide['week'] = WEEK

schedule_w2_wide

def get_schedule_by_week(league_id, week):
    matchup_url = f'https://api.sleeper.app/v1/league/{league_id}/matchups/{week}'
    matchup_json = requests.get(matchup_url).json()

    team_sched = DataFrame([proc_team_schedule(team) for team in matchup_json])

    team_sched_wide = pd.merge(
        team_sched.drop_duplicates('game_id', keep='first'),
        team_sched.drop_duplicates('game_id', keep='last'), on='game_id')

    team_sched_wide.rename(
        columns={'team_id_x': 'team1_id', 'team_id_y': 'team2_id'},
        inplace=True)

    team_sched_wide['season'] = 2021
    team_sched_wide['week'] = week
    return team_sched_wide

get_schedule_by_week(LEAGUE_ID, 3)

settings_json['settings']['playoff_week_start']

def get_league_schedule(league_id):
    settings_url = f'https://api.sleeper.app/v1/league/{LEAGUE_ID}'
    settings_json = requests.get(settings_url).json()

    n = settings_json['settings']['playoff_week_start']
    return pd.concat(
        [get_schedule_by_week(league_id, x) for x in range(1, n)], ignore_index=True)

league_schedule = get_league_schedule(LEAGUE_ID)
