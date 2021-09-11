import requests
import numpy as np
from pathlib import Path
from os import path
from textwrap import dedent
from pandas import DataFrame, Series
import pandas as pd
from utilities import (LICENSE_KEY, generate_token, master_player_lookup,
                       YAHOO_FILE, YAHOO_KEY, YAHOO_SECRET)
from yahoo_oauth import OAuth2
import sqlite3
import json

pd.options.mode.chained_assignment = None

####################
# handle yahoo oauth
####################

if not Path(YAHOO_FILE).exists():
    yahoo_credentials_dict = {
        'consumer_key': YAHOO_FILE,
        'consumer_secret': YAHOO_KEY,
    }
    with open(YAHOO_FILE, 'w') as f:
        json.dump(yahoo_credentials_dict, f)

OAUTH =  OAuth2(None, None, from_file=YAHOO_FILE)

######################
# top level functions:
######################


def get_league_rosters(lookup, league_id, week):
    teams = get_teams_in_league(league_id=league_id)

    league_rosters = pd.concat(
        [_get_team_roster(x, league_id, week, lookup) for x in
         teams['team_id']], ignore_index=True)
    league_rosters['team_position'].replace({'W/R/T': 'WR/RB/TE'}, inplace=True)
    return league_rosters

def get_teams_in_league(league_id):
    teams_url = ('https://fantasysports.yahooapis.com/fantasy/v2/' +
                f'league/406.l.{league_id}' +
                ';out=metadata,settings,standings,scoreboard,teams,players,draftresults,transactions')

    teams_json = (OAUTH
                 .session
                 .get(teams_url, params={'format': 'json'})
                 .json())

    teams_dict = (teams_json['fantasy_content']
                  ['league'][2]['standings'][0]['teams'])

    teams_df = DataFrame([_process_team(team) for key, team in
                          teams_dict.items() if key != 'count'])

    teams_df['league_id'] = league_id
    return teams_df

def get_league_schedule(league_id):
    league_teams = get_teams_in_league(league_id=league_id)

    schedule_by_team = pd.concat([_get_schedule_by_team(x, league_id) for
                                  x in league_teams['team_id']],
                                   ignore_index=True)

    schedule_by_week = schedule_by_team.drop_duplicates('matchup_id')

    schedule_by_week.columns = ['team1_id', 'team2_id', 'week', 'matchup_id',
                                'season']
    return schedule_by_week


##################
# helper functions
##################

# roster helper functions

def _process_player(player):
    player_info = _yahoo_list_to_dict(player, 'player')
    pos_info = player['player'][1]['selected_position'][1]

    dict_to_return = {}
    dict_to_return['yahoo_id'] = int(player_info['player_id'])
    dict_to_return['name'] = player_info['name']['full']
    dict_to_return['player_position'] = player_info['primary_position']
    dict_to_return['team_position'] = pos_info['position']

    return dict_to_return

def _add_pos_suffix(df_subset):
    if len(df_subset) > 1:
        suffix = Series(range(1, len(df_subset) + 1), index=df_subset.index)

        df_subset['team_position'] = (
          df_subset['team_position'] + suffix.astype(str))
    return df_subset


def _process_players(players):
    players_raw = DataFrame(
        [_process_player(player) for key, player in players.items() if key !=
         'count' ])

    players_df = pd.concat([
        _add_pos_suffix(players_raw.query(f"team_position == '{x}'"))
        for x in players_raw['team_position'].unique()])

    players_df['start'] = ~(players_df['team_position'].str.startswith('BN') |
                            players_df['team_position'].str.startswith('IR'))

    return players_df


def _process_roster(team):
    players_df = _process_players(team[1]['roster']['0']['players'])
    team_id = team[0][1]['team_id']

    players_df['team_id'] = team_id
    return players_df


def _get_team_roster(team_id, league_id, week, lookup):
    roster_url = ('https://fantasysports.yahooapis.com/fantasy/v2' +
                  f'/team/406.l.{league_id}.t.{team_id}/roster;week={week}')

    roster_json = OAUTH.session.get(roster_url, params={'format': 'json'}).json()

    roster_df = _process_roster(roster_json['fantasy_content']['team'])

    # stats
    points_url = ('https://fantasysports.yahooapis.com/fantasy/v2/' +
                    f'team/406.l.{LEAGUE_ID}.t.{team_id}' +
                "/players;out=metadata,stats,ownership,percent_owned,draft_analysis")
    points_json = OAUTH.session.get(points_url, params={'format': 'json'}).json()

    player_dict = points_json['fantasy_content']['team'][1]['players']
    stats = _process_team_stats(player_dict)
    roster_df_w_stats = pd.merge(roster_df, stats)

    roster_df_w_id = pd.merge(roster_df_w_stats,
                            lookup[['fantasymath_id', 'yahoo_id']],
                            how='left').drop('yahoo_id', axis=1)

    return roster_df_w_id

def _process_player_stats(player):
    dict_to_return = {}
    dict_to_return['yahoo_id'] = int(player['player'][0][1]['player_id'])
    dict_to_return['actual'] = float(
        player['player'][1]['player_points']['total'])
    return dict_to_return

def _process_team_stats(team):
    stats = DataFrame([_process_player_stats(player) for key, player in
                       team.items() if key != 'count'])
    stats.loc[stats['actual'] == 0, 'actual'] = np.nan
    return stats
###############################################################################
# team data
###############################################################################

def _yahoo_list_to_dict(yahoo_list, key):
    return_dict = {}
    for x in yahoo_list[key][0]:
        if (type(x) is dict) and (len(x.keys()) == 1):
                for key_ in x.keys():  # tricky way to get access to key
                    return_dict[key_] = x[key_]
    return return_dict

def _process_team(team):
    team_dict = _yahoo_list_to_dict(team, 'team')
    owner_dict = team_dict['managers'][0]['manager']

    dict_to_return = {}
    dict_to_return['team_id'] = team_dict['team_id']
    dict_to_return['owner_id'] = owner_dict['guid']
    dict_to_return['owner_name'] = owner_dict['nickname']
    return dict_to_return

def _make_matchup_id(season, week, team1, team2):
    teams = [team1, team2]
    teams.sort()

    return int(str(season) + str(week).zfill(2) +
                     str(teams[0]).zfill(2) + str(teams[1]).zfill(2))

def _process_matchup(matchup):
    team0 = _yahoo_list_to_dict(matchup['matchup']['0']['teams']['0'], 'team')
    team1 = _yahoo_list_to_dict(matchup['matchup']['0']['teams']['1'], 'team')

    dict_to_return = {}
    dict_to_return['team_id'] = team0['team_id']
    dict_to_return['opp_id'] = team1['team_id']
    dict_to_return['week'] = matchup['matchup']['week']
    dict_to_return['matchup_id'] = _make_matchup_id(
        2021, matchup['matchup']['week'], team0['team_id'], team1['team_id'])

    return dict_to_return

def _get_schedule_by_team(team_id, league_id):
    schedule_url = ('https://fantasysports.yahooapis.com/fantasy/v2/' +
                    f'team/406.l.{league_id}.t.{team_id}' +
                    ';out=matchups')

    schedule_raw = OAUTH.session.get(schedule_url, params={'format': 'json'}).json()
    matchup_dict = schedule_raw['fantasy_content']['team'][1]['matchups']
    df =  DataFrame([_process_matchup(matchup)
            for key, matchup
            in matchup_dict.items()
            if key != 'count'])
    df['season'] = 2021
    return df

CONSUMER_KEY =  "dj0yJmk9VTZhWktxQU81Z3lqJmQ9WVdrOVVHOUNaa3ROUTFFbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWVk"
CONSUMER_SECRET = "56ec294a542df43a5660a296e86deaaa1eff00c8"

if __name__ == '__main__':

    LEAGUE_ID = 43886
    WEEK = 1
    token = generate_token(LICENSE_KEY)['token']
    lookup = master_player_lookup(token)

    rosters = get_league_rosters(lookup, LEAGUE_ID, WEEK)
    teams = get_teams_in_league(LEAGUE_ID)
    schedule = get_league_schedule(LEAGUE_ID)
