import requests
from textwrap import dedent
from pandas import DataFrame, Series
import pandas as pd
from utilities import (LICENSE_KEY, generate_token, master_player_lookup, SWID,
                       ESPN_S2)
import sqlite3
import json
pd.options.mode.chained_assignment = None


############
# parameters
############

LEAGUE_ID = 242906
TEAM_ID = 11

###############################################################################
# roster data
###############################################################################
roster_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
              f'/segments/0/leagues/{LEAGUE_ID}?view=mRoster')

# gets current data
# should run/look at, but we're overwriting with saved data next line
roster_json = requests.get(roster_url, cookies={'swid': SWID, 'espn_s2':
                                                ESPN_S2}).json()

# saved data
with open('./projects/integration/raw/espn/roster.json') as f:
    roster_json = json.load(f)

list_of_rosters = roster_json['teams']

roster0 = list_of_rosters[0]
roster0

list_of_players_on_roster0 = roster0['roster']['entries']
roster0_player0 = list_of_players_on_roster0[0]
roster0_player0.keys()

def process_player1(player):
    dict_to_return = {}
    dict_to_return['team_position'] = player['lineupSlotId']
    dict_to_return['espn_id'] = player['playerId']

    dict_to_return['name'] = player['playerPoolEntry']['player']['fullName']
    dict_to_return['player_position'] = player['playerPoolEntry']['player']['defaultPositionId']
    return dict_to_return

process_player1(roster0_player0)

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

def process_player2(player):
    dict_to_return = {}
    dict_to_return['team_position'] = TEAM_POSITION_MAP[player['lineupSlotId']]
    dict_to_return['espn_id'] = player['playerId']

    dict_to_return['name'] = player['playerPoolEntry']['player']['fullName']
    dict_to_return['player_position'] = (
        PLAYER_POSITION_MAP[
            player['playerPoolEntry']['player']['defaultPositionId']])
    return dict_to_return

[process_player2(x) for x in list_of_players_on_roster0]

roster0_df = DataFrame([process_player2(x) for x in
                        list_of_players_on_roster0])

roster0_df

# handling duplicate team_position
wrs = roster0_df.query("team_position == 'WR'")
suffix = Series(range(1, len(wrs) + 1), index=wrs.index)
wrs['team_position'] + suffix.astype(str)

def add_pos_suffix(df_subset):
    if len(df_subset) > 1:
        suffix = Series(range(1, len(df_subset) + 1), index=df_subset.index)

        df_subset['team_position'] = df_subset['team_position'] + suffix.astype(str)
    return df_subset

roster0_df2 = pd.concat([
    add_pos_suffix(roster0_df.query(f"team_position == '{x}'"))
    for x in roster0_df['team_position'].unique()])

roster0_df2

roster0_df2['start'] = ~roster0_df2['team_position'].str.startswith('BE')
roster0_df2

def process_players(entries):
    roster_df = DataFrame([process_player2(x) for x in entries])

    roster_df2 = pd.concat([
        add_pos_suffix(roster_df.query(f"team_position == '{x}'"))
        for x in roster_df['team_position'].unique()])

    roster_df2['start'] = ~roster_df2['team_position'].str.startswith('BE')

    return roster_df2

process_players(list_of_players_on_roster0)

roster1 = list_of_rosters[1]

roster1['id']
process_players(roster1['roster']['entries']).head()

def process_roster(team):
    roster_df = process_players(team['roster']['entries'])
    team_id = team['id']

    roster_df['team_id'] = team_id
    return roster_df

all_rosters = pd.concat([process_roster(x) for x in list_of_rosters],
                        ignore_index=True)

boxscore_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                f'/segments/0/leagues/{LEAGUE_ID}?view=mBoxscore')

# gets current points data
# should run/look at, but we're overwriting with saved data next line
boxscore_json = requests.get(boxscore_url, cookies={'swid': SWID, 'espn_s2':
                                                    ESPN_S2}).json()

# saved data
with open('./projects/integration/raw/espn/boxscore.json') as f:
    boxscore_json = json.load(f)

matchup_list = boxscore_json['schedule']
matchup0 = matchup_list[0]

matchup0_home0 = matchup0['home']['rosterForMatchupPeriod']['entries'][0]

def proc_played(played):
    dict_to_return = {}
    dict_to_return['espn_id'] = played['playerId']

    dict_to_return['actual'] = played['playerPoolEntry']['player']['stats'][0]['appliedTotal']
    return dict_to_return

proc_played(matchup0_home0)

def proc_played_team(team):
    if 'rosterForMatchupPeriod' in team.keys():
        return DataFrame([proc_played(x) for x in
                          team['rosterForMatchupPeriod']['entries']])
    else:
        return DataFrame()

def proc_played_matchup(matchup):
    return pd.concat([proc_played_team(matchup['home']),
                      proc_played_team(matchup['away'])], ignore_index=True)

scores = pd.concat([proc_played_matchup(x) for x in matchup_list])

all_rosters_w_pts = pd.merge(all_rosters, scores, how='left')

# fantasy math id
all_rosters_w_pts['name'].str.lower().str.replace(' ','-').head()

from utilities import (LICENSE_KEY, generate_token, master_player_lookup)

token = generate_token(LICENSE_KEY)['token']
fantasymath_players = master_player_lookup(token)

fantasymath_players = pd.read_csv('./projects/integration/raw/lookup.csv')

fantasymath_players.head()

all_rosters_w_id = pd.merge(all_rosters_w_pts,
                            fantasymath_players[['fantasymath_id', 'espn_id']],
                            how='left')

all_rosters_final = all_rosters_w_id.drop('espn_id', axis=1)
all_rosters_final.sample(10)

def get_league_rosters(lookup, league_id):
    roster_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                  f'/segments/0/leagues/{league_id}?view=mRoster')

    roster_json = requests.get(roster_url,
                             cookies={'swid': SWID, 'espn_s2': ESPN_S2}).json()

    all_rosters = pd.concat([process_roster(x) for x in roster_json['teams']],
                            ignore_index=True)

    # score part
    boxscore_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                    f'/segments/0/leagues/{league_id}?view=mBoxscore')
    boxscore_json = requests.get(boxscore_url, cookies={'swid': SWID, 'espn_s2':
                                                        ESPN_S2}).json()
    matchup_list = boxscore_json['schedule']
    scores = pd.concat([proc_played_matchup(x) for x in matchup_list])

    all_rosters = pd.merge(all_rosters, scores, how='left')


    all_rosters_w_id = pd.merge(all_rosters,
                                lookup[['fantasymath_id', 'espn_id']],
                                how='left').drop('espn_id', axis=1)

    return all_rosters_w_id

complete_league_rosters = get_league_rosters(fantasymath_players, LEAGUE_ID)

###############################################################################
# team data
###############################################################################

teams_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
             f'/segments/0/leagues/{LEAGUE_ID}?view=mTeam')

teams_json = requests.get(teams_url, cookies={'swid': SWID, 'espn_s2':
                                              ESPN_S2}).json()

with open('./projects/integration/raw/espn/teams.json') as f:
    teams_json = json.load(f)

teams_list = teams_json['teams']
members_list = teams_json['members']

def process_team(team):
    dict_to_return = {}
    dict_to_return['team_id'] = team['id']
    dict_to_return['owner_id'] = team['owners'][0]
    return dict_to_return

def process_member(member):
    dict_to_return = {}
    dict_to_return['owner_id'] = member['id']
    dict_to_return['owner_name'] = member['displayName']
    return dict_to_return

DataFrame([process_team(team) for team in teams_list])
DataFrame([process_member(member) for member in members_list])

def get_teams_in_league(league_id):
    teams_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                f'/segments/0/leagues/{league_id}?view=mTeam')

    teams_json = requests.get(teams_url, cookies={'swid': SWID, 'espn_s2':
                                                  ESPN_S2}).json()
    teams_list = teams_json['teams']
    members_list = teams_json['members']

    teams_df = DataFrame([process_team(team) for team in teams_list])
    member_df = DataFrame([process_member(member) for member in members_list])

    comb = pd.merge(teams_df, member_df)
    comb['league_id'] = league_id

    return comb

league_teams = get_teams_in_league(LEAGUE_ID)

###############################################################################
# schedule
###############################################################################

schedule_url = ('https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021' +
                f'/segments/0/leagues/{LEAGUE_ID}?view=mBoxscore')

schedule_json = requests.get(schedule_url, cookies={'swid': SWID, 'espn_s2':
                                                    ESPN_S2}).json()

with open('./projects/integration/raw/espn/schedule.json') as f:
    schedule_json = json.load(f)

matchup_list = schedule_json['schedule']

matchup0 = matchup_list[0]

matchup0['id']  # matchup_id
matchup0['home']['teamId']  # "home" team_id
matchup0['away']['teamId']  # "away" team_id
matchup0['matchupPeriodId'] # week

def process_matchup(matchup):
    dict_to_return = {}

    dict_to_return['matchup_id'] = matchup['id']  # matchup_id
    dict_to_return['home_id'] = matchup['home']['teamId']  # "home" team_id
    dict_to_return['away_id'] = matchup['away']['teamId']  # "away" team_id
    dict_to_return['week'] = matchup['matchupPeriodId'] # week

    return dict_to_return

matchup_df = DataFrame([process_matchup(matchup) for matchup in matchup_list])
matchup_df.head(10)

def get_league_schedule(league_id):
    schedule_url = f'https://fantasy.espn.com/apis/v3/games/ffl/seasons/2021/segments/0/leagues/{LEAGUE_ID}?view=mBoxscore'

    schedule_json = requests.get(schedule_url, cookies={'swid': SWID, 'espn_s2':
                                                        ESPN_S2}).json()
    matchup_list = schedule_json['schedule']

    matchup_df = DataFrame([process_matchup(matchup) for matchup in matchup_list])
    matchup_df['league_id'] = league_id
    matchup_df['season'] = 2021
    matchup_df.rename(columns={'home_id': 'team1_id', 'away_id': 'team2_id'},
                      inplace=True)
    return matchup_df

league_schedule = get_league_schedule(LEAGUE_ID)
league_schedule.head()
