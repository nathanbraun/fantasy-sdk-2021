import requests
from pandas import DataFrame
import pandas as pd

def player_dict(slot):
    if 'leaguePlayer' in slot.keys():
        fleaflicker_player_dict = slot['leaguePlayer']['proPlayer']

        dict_to_return = {}
        dict_to_return['name'] = fleaflicker_player_dict['nameFull']
        dict_to_return['position'] = fleaflicker_player_dict['position']
        dict_to_return['fleaflicker_id'] = fleaflicker_player_dict['id']

        return dict_to_return
    else:
        return {'position': slot['position']['label']}

def lineup_by_team_week(league_id, team_id, week, season):
    team_url = (
        'https://www.fleaflicker.com/api/FetchRoster?' +
        f'leagueId={league_id}&teamId={team_id}&season={season}&scoringPeriod=1')

    response = requests.get(team_url)
    response_json = response.json()

    starters = response_json['groups'][0]['slots']
    bench = response_json['groups'][1]['slots']

    starter_df = DataFrame([player_dict(x) for x in starters])
    bench_df = DataFrame([player_dict(x) for x in bench])

    starter_df['start'] = True
    bench_df['start'] = False

    lineup_df = pd.concat([starter_df, bench_df], ignore_index=True)

    lineup_df['team_id'] = team_id
    lineup_df['week'] = week
    lineup_df['season'] = season

    return lineup_df

def team_from_div(team):
    dict_to_return = {}

    dict_to_return['team_id'] = team['id']
    dict_to_return['owner_id'] = team['owners'][0]['id']
    dict_to_return['owner_name'] = team['owners'][0]['displayName']

    return dict_to_return

def teams_from_div(division):
    return_df = DataFrame([team_from_div(x) for x in division['teams']])
    return_df['division_id'] = division['id']
    return return_df

def teams_from_divs(divisions):
    return pd.concat([teams_from_div(division) for division in divisions], ignore_index=True)

def team_info_by_year(league_id, season):
    league_url = f'https://www.fleaflicker.com/api/FetchLeagueStandings?leagueId={league_id}&season={season}'

    response = requests.get(league_url)
    response_json = response.json()

    teams = teams_from_divs(response_json['divisions'])
    teams['season'] = season
    return teams

def matchup_info(game):
    return_dict = {}
    return_dict['home_id'] = game['home']['id']
    return_dict['away_id'] = game['away']['id']
    return_dict['game_id'] = game['id']
    return return_dict

def matchup_by_league_week(league_id, week, season):
    matchup_url = (
        'https://www.fleaflicker.com/api/FetchLeagueScoreboard?' +
        f'leagueId={league_id}&scoringPeriod={week}&season={season}')

    response = requests.get(matchup_url)
    response_json = response.json()

    matchup_df = DataFrame([matchup_info(x) for x in response_json['games']])
    matchup_df['season'] = season
    matchup_df['week'] = week
    matchup_df['league_id'] = league_id
    return matchup_df

def schedule_by_league_season(league_id, season):
    return pd.concat([matchup_by_league_week(league_id, week, season) for week in
                      range(1, 15)], ignore_index=True)
