import requests
from textwrap import dedent
from pandas import DataFrame, Series
import pandas as pd
from utilities import (LICENSE_KEY, generate_token, master_player_lookup, SWID,
                       ESPN_S2)
import sqlite3
import json

pd.options.mode.chained_assignment = None

######################
# top level functions:
######################

def get_league_rosters(lookup, league_id, week=None):
    roster_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                  f'/segments/0/leagues/{league_id}?view=mRoster')

    roster_json = requests.get(roster_url,
                             cookies={'swid': SWID, 'espn_s2': ESPN_S2}).json()

    all_rosters = pd.concat([_process_roster(x) for x in roster_json['teams']],
                            ignore_index=True)

    # score part
    boxscore_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                    f'/segments/0/leagues/{league_id}?view=mBoxscore')
    boxscore_json = requests.get(boxscore_url, cookies={'swid': SWID, 'espn_s2':
                                                        ESPN_S2}).json()
    matchup_list = boxscore_json['schedule']
    scores = pd.concat([_proc_played_matchup(x) for x in matchup_list])

    all_rosters = pd.merge(all_rosters, scores, how='left')

    all_rosters_w_id = pd.merge(all_rosters,
                                lookup[['fantasymath_id', 'espn_id']],
                                how='left').drop('espn_id', axis=1)

    return all_rosters_w_id

def get_teams_in_league(league_id):
    teams_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                f'/segments/0/leagues/{league_id}?view=mTeam')

    teams_json = requests.get(teams_url, cookies={'swid': SWID, 'espn_s2':
                                                  ESPN_S2}).json()
    teams_list = teams_json['teams']
    members_list = teams_json['members']

    teams_df = DataFrame([_process_team(team) for team in teams_list])
    member_df = DataFrame([_process_member(member) for member in members_list])

    comb = pd.merge(teams_df, member_df)
    comb['league_id'] = league_id

    return comb

def get_league_schedule(league_id):
    schedule_url = f'https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021/segments/0/leagues/{league_id}?view=mBoxscore'

    schedule_json = requests.get(schedule_url, cookies={'swid': SWID, 'espn_s2':
                                                        ESPN_S2}).json()
    matchup_list = schedule_json['schedule']

    matchup_df = DataFrame([_process_matchup(matchup) for matchup in matchup_list])
    matchup_df['league_id'] = league_id
    matchup_df['season'] = 2021
    matchup_df.rename(columns={'home_id': 'team1_id', 'away_id': 'team2_id'},
                      inplace=True)
    return matchup_df

##################
# helper functions
##################

# roster helper functions

TEAM_POSITION_MAP = {
    0: 'QB', 1: 'TQB', 2: 'RB', 3: 'RB/WR', 4: 'WR', 5: 'WR/TE',
    6: 'TE', 7: 'OP', 8: 'DT', 9: 'DE', 10: 'LB', 11: 'DL',
    12: 'CB', 13: 'S', 14: 'DB', 15: 'DP', 16: 'D/ST', 17: 'K',
    18: 'P', 19: 'HC', 20: 'BE', 21: 'IR', 22: '', 23: 'RB/WR/TE',
    24: 'ER', 25: 'Rookie', 'QB': 0, 'RB': 2, 'WR': 4, 'TE': 6,
    'D/ST': 16, 'K': 17, 'FLEX': 23, 'DT': 8, 'DE': 9, 'LB': 10,
    'DL': 11, 'CB': 12, 'S': 13, 'DB': 14, 'DP': 15, 'HC': 19
}

PLAYER_POSITION_MAP = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'D/ST'}

def _process_player(player):
    dict_to_return = {}
    dict_to_return['team_position'] = TEAM_POSITION_MAP[player['lineupSlotId']]
    dict_to_return['espn_id'] = player['playerId']

    dict_to_return['name'] = player['playerPoolEntry']['player']['fullName']
    dict_to_return['player_position'] = (
        PLAYER_POSITION_MAP[
            player['playerPoolEntry']['player']['defaultPositionId']])
    return dict_to_return

def _add_pos_suffix(df_subset):
    if len(df_subset) > 1:
        suffix = Series(range(1, len(df_subset) + 1), index=df_subset.index)

        df_subset['team_position'] = df_subset['team_position'] + suffix.astype(str)
    return df_subset


def _process_players(entries):
    roster_df = DataFrame([_process_player(x) for x in entries])

    roster_df2 = pd.concat([
        _add_pos_suffix(roster_df.query(f"team_position == '{x}'"))
        for x in roster_df['team_position'].unique()])

    roster_df2['start'] = ~roster_df2['team_position'].str.startswith('BE')

    return roster_df2


def _process_roster(team):
    roster_df = _process_players(team['roster']['entries'])
    team_id = team['id']

    roster_df['team_id'] = team_id
    return roster_df

def _proc_played(played):
    dict_to_return = {}
    dict_to_return['espn_id'] = played['playerId']

    dict_to_return['actual'] = played['playerPoolEntry']['player']['stats'][0]['appliedTotal']
    return dict_to_return

def _proc_played_team(team):
    if 'rosterForMatchupPeriod' in team.keys():
        return DataFrame([_proc_played(x) for x in
                          team['rosterForMatchupPeriod']['entries']])
    else:
        return DataFrame()

def _proc_played_matchup(matchup):
    return pd.concat([_proc_played_team(matchup['home']),
                      _proc_played_team(matchup['away'])], ignore_index=True)

# team helper functions
def _process_team(team):
    dict_to_return = {}
    dict_to_return['team_id'] = team['id']
    dict_to_return['owner_id'] = team['owners'][0]
    return dict_to_return

def _process_member(member):
    dict_to_return = {}
    dict_to_return['owner_id'] = member['id']
    dict_to_return['owner_name'] = member['displayName']
    return dict_to_return


# schedule helper functions

def _process_matchup(matchup):
    dict_to_return = {}

    dict_to_return['matchup_id'] = matchup['id']  # matchup_id
    dict_to_return['home_id'] = matchup['home']['teamId']  # "home" team_id
    dict_to_return['away_id'] = matchup['away']['teamId']  # "away" team_id
    dict_to_return['week'] = matchup['matchupPeriodId'] # week

    return dict_to_return

if __name__ == '__main__':
    ############
    # parameters
    ############

    LEAGUE_ID = 242906

    ESPN_PARAMETERS = {'league_id': LEAGUE_ID,
                    'swid': SWID,
                    'espn_s2': ESPN_S2}

    token = generate_token(LICENSE_KEY)['token']
    lookup = master_player_lookup(token)

    rosters = get_league_rosters(lookup, LEAGUE_ID)
    teams = get_teams_in_league(LEAGUE_ID)
    schedule = get_league_schedule(LEAGUE_ID)
