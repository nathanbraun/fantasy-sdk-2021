import requests
import numpy as np
from textwrap import dedent
from pandas import DataFrame, Series
import pandas as pd
import sqlite3
from utilities import (LICENSE_KEY, generate_token, master_player_lookup,
                       DB_PATH, API_URL)
import json
pd.options.mode.chained_assignment = None

######################
# top level functions:
######################
def get_league_rosters(lookup, league_id, week):
    matchup_url = f'https://api.sleeper.app/v1/league/{league_id}/matchups/{week}'
    matchup_json = requests.get(matchup_url).json()

    settings_url = f'https://api.sleeper.app/v1/league/{league_id}'
    settings_json = requests.get(settings_url).json()

    return pd.concat([_get_team_roster(x, lookup,
                                      settings_json['roster_positions']) for x
                      in matchup_json], ignore_index=True)

def get_teams_in_league(league_id):
    teams_url = f'https://api.sleeper.app/v1/league/{league_id}/users'
    teams_json = requests.get(teams_url).json()

    all_teams = DataFrame(
        [_proc_team(team, i) for i, team in enumerate(teams_json, start=1)])
    all_teams['league_id'] = league_id
    return all_teams

def get_league_schedule(league_id):
    settings_url = f'https://api.sleeper.app/v1/league/{league_id}'
    settings_json = requests.get(settings_url).json()

    n = settings_json['settings']['playoff_week_start']
    return pd.concat(
        [_get_schedule_by_week(league_id, x) for x in range(1, n)], ignore_index=True)

##################
# helper functions
##################

def _get_team_roster(team, lookup, positions):
    # starters
    starters = Series(team['starters']).to_frame('sleeper_id')

    starters_w_info = pd.merge(starters, lookup, how='left')
    starters_w_info['actual'] = team['starters_points']
    starters_w_info.loc[starters_w_info['actual'] == 0, 'actual'] = np.nan
    starters_w_info['team_position'] = [x for x in positions if x != 'BN']

    starters_pos = pd.concat([
        _add_pos_suffix(starters_w_info.query(f"team_position == '{x}'"))
        for x in starters_w_info['team_position'].unique()])

    players = Series(team['players']).to_frame('sleeper_id')
    players_w_info = pd.merge(players, lookup, how='left')

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

def _get_schedule_by_week(league_id, week):
    matchup_url = f'https://api.sleeper.app/v1/league/{league_id}/matchups/{week}'
    matchup_json = requests.get(matchup_url).json()

    team_sched = DataFrame([_proc_team_schedule(team) for team in matchup_json])

    team_sched_wide = pd.merge(
        team_sched.drop_duplicates('game_id', keep='first'),
        team_sched.drop_duplicates('game_id', keep='last'), on='game_id')

    team_sched_wide.rename(
        columns={'team_id_x': 'team1_id', 'team_id_y': 'team2_id'},
        inplace=True)

    team_sched_wide['season'] = 2021
    team_sched_wide['week'] = week
    return team_sched_wide

def _add_pos_suffix(df_subset):
    if len(df_subset) > 1:
        suffix = Series(range(1, len(df_subset) + 1), index=df_subset.index)

        df_subset['team_position'] = df_subset['team_position'] + suffix.astype(str)
    return df_subset

def _proc_team(team, team_id):
    dict_to_return = {}

    dict_to_return['owner_id'] = team['user_id']
    dict_to_return['owner_name'] = team['display_name']
    dict_to_return['team_id'] = team_id
    return dict_to_return

def _proc_team_schedule(team):
    dict_to_return = {}
    dict_to_return['team_id'] = team['roster_id']
    dict_to_return['game_id'] = team['matchup_id']
    return dict_to_return

if __name__ == '__main__':
    league_id = 717250053961510912
    week = 3

    token = generate_token(LICENSE_KEY)['token']
    lookup = master_player_lookup(token)

    teams = get_teams_in_league(league_id)
    schedule = get_league_schedule(league_id)
    rosters = get_league_rosters(lookup, league_id, week)
