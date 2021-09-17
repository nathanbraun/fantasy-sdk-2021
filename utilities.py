from pandas import DataFrame, Series
import pandas as pd
import json
from os import path
from textwrap import dedent
import requests
from pathlib import Path
from configparser import ConfigParser

config = ConfigParser(interpolation=None)
config.read('config.ini')

################################################################################
# shouldn't have to change anything in this file
# this file reads your config.ini and assigns values based on that
# do not edit them here
################################################################################

# constants - mostly loaded from config.ini - shouldn't need to change
# if not working make sure you have config.ini set up
API_URL = 'https://api.sims.fantasymath.com'

LICENSE_KEY = config['sdk']['LICENSE_KEY']
OUTPUT_PATH = config['sdk']['OUTPUT_PATH']
DB_PATH = config['sdk']['DB_PATH']

# league integration
# yahoo
YAHOO_FILE = config['yahoo']['FILE']
YAHOO_KEY =  config['yahoo']['KEY']
YAHOO_SECRET = config['yahoo']['SECRET']

# espn
SWID = config['espn']['SWID']
ESPN_S2 = config['espn']['ESPN_S2']

################################################################################
# auth functions
################################################################################

def generate_token(license):
    """
    Given some license key, validates it with the API endpoint, and — if
    successfully validated — returns an access token good for 24 hours.
    """
    query_token = dedent(
        f"""
        query {{
            token (license: "{license}") {{
                success,
                message,
                token
            }}
            }}
        """)

    r = requests.post(API_URL, json={'query': query_token})
    return json.loads(r.text)['data']['token']

def validate(token):
    """
    Can use this function to test whether your access token is working
    correctly.
    """
    query_validate = ("""
                      query {
                        validate {
                            validated,
                            message
                        }
                      }
                      """)

    r = requests.post(API_URL, json={'query': query_validate},
                  headers={'Authorization': f'Bearer {token}'})
    return json.loads(r.text)['data']

################################################################################
# player functions
################################################################################

def master_player_lookup(token):
    query_players = """
        query {
            players {
                fantasymath_id,
                position,
                fleaflicker_id,
                espn_id,
                yahoo_id
            }
        }
        """

    r = requests.post(API_URL, json={'query': query_players},
                  headers={'Authorization': f'Bearer {token}'})

    raw = json.loads(r.text)['data']

    if raw is None:
        print("Something went wrong. No data.")
        return DataFrame()
    else:
        return DataFrame(raw['players'])


def get_players(token,  qb='pass6', skill='ppr', dst='high', week=None,
                      season=2021):

    _check_arg('qb scoring', qb, ['pass6', 'pass4'])
    _check_arg('rb/wr/te scoring', skill, ['ppr', 'ppr0'])
    _check_arg('dst scoring', dst, ['high', 'mfl'])


    arg_string = f'qb: "{qb}", skill: "{skill}", dst: "{dst}", season: {season}'

    if week is not None:
        arg_string = arg_string + f', week: {week}'

    if season < 2021:
        query_available = dedent(
            f"""
            query {{
                available({arg_string}) {{
                    fantasymath_id,
                    position,
                    actual
                }}
            }}
            """)
    else:
        query_available = dedent(
            f"""
            query {{
                available({arg_string}) {{
                    fantasymath_id,
                    position,
                    fleaflicker_id,
                    espn_id,
                    yahoo_id,
                    sleeper_id
                }}
            }}
            """)

    r = requests.post(API_URL, json={'query': query_available},
                  headers={'Authorization': f'Bearer {token}'})

    raw = json.loads(r.text)['data']

    if raw is None:
        print("Something went wrong. No data.")
        return DataFrame()
    else:
        return DataFrame(raw['available'])


def _check_arg(name, arg, allowed, none_ok=False):
    """
    Helper function to make sure argument is allowed.
    """
    if not ((arg in allowed) or (none_ok and arg is None)):
        raise ValueError(f"Invalid {name} argument. Needs to be in {allowed}.")

def get_sims(token, players, qb='pass6', skill='ppr', dst='high', week=None,
             season=2021, nsims=100):

    ###########################
    # check for valid arguments
    ###########################
    _check_arg('week', week, range(1, 17), none_ok=True)
    _check_arg('season', season, range(2017, 2022))
    _check_arg('qb scoring', qb, ['pass6', 'pass4'])
    _check_arg('rb/wr/te scoring', skill, ['ppr', 'ppr0'])
    _check_arg('dst scoring', dst, ['high', 'mfl'])

    player_str = ','.join([f'"{x}"' for x in players])

    if week is None:
        query = f"""
            query {{
                sims(qb: "{qb}", skill: "{skill}", dst: "{dst}", nsims: {nsims},
                    fantasymath_ids: [{player_str}]) {{
                    players {{
                        fantasymath_id
                        sims
                    }}
                }}
            }}
            """
        endpoint = 'sims'

    else:
        query = f"""
            query {{
                historical(week: {week}, season: {season}, qb: "{qb}", skill:
                    "{skill}", dst: "{dst}", nsims: {nsims},
                    fantasymath_ids: [{player_str}]) {{
                    players {{
                        fantasymath_id
                        sims
                    }}
                }}
            }}
            """
        endpoint = 'historical'

    # send request
    r = requests.post(API_URL, json={'query': query},
                  headers={'Authorization': f'Bearer {token}'})
    raw = json.loads(r.text)['data']

    if raw is None:
        print("No data. Check token.")
        return DataFrame()
    else:
        return pd.concat([Series(x['sims']).to_frame(x['fantasymath_id']) for x in
                          raw[endpoint]['players']], axis=1)


# misc helper

def schedule_long(sched):
    sched1 = sched.rename(columns={'team1_id': 'team_id', 'team2_id':
                                      'opp_id'})
    sched2 = sched.rename(columns={'team2_id': 'team_id', 'team1_id':
                                      'opp_id'})
    return pd.concat([sched1, sched2], ignore_index=True)

if __name__ == '__main__':
    # generate access token
    token = generate_token(LICENSE_KEY)['token']

    # validate it
    validate(token)

    # raw graphql example
    QUERY_STR = """
        query {
            available(week: 1, season: 2019) {
                fantasymath_id,
                position,
                actual
            }
        }
        """

    r = requests.post(API_URL, json={'query': QUERY_STR},
                    headers={'Authorization': f'Bearer {token}'})
    df = DataFrame(json.loads(r.text)['data']['available'])
