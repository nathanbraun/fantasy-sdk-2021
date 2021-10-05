import hosts.fleaflicker as site
import hosts.db as db
from os import path
import datetime as dt
from pandas import DataFrame, Series
import sqlite3
import wdis_manual as wdis
import pandas as pd
from pathlib import Path
from os import path
from utilities import (LICENSE_KEY, generate_token, master_player_lookup,
                       get_sims, get_players, DB_PATH, OUTPUT_PATH,
                       schedule_long)

# enter your league ID info here
# used to get correct data out of db
# note: you NEED to have run `create_league.py` on whatever you do here
LEAGUE_ID = 34958
WEEK = 2

def wdis_by_pos(pos, sims, roster, opponent_starters):
    wdis_options = wdis_options_by_pos(roster, pos)

    starters = list(roster.loc[rosters['start'] &
                               rosters['fantasymath_id'].notnull(),
                               'fantasymath_id'])

    df = wdis.calculate(sims, starters, opponent_starters, set(wdis_options) &
                        set(sims.columns))

    df['pos'] = pos
    df.index.name = 'player'
    df.reset_index(inplace=True)
    df.set_index(['pos', 'player'], inplace=True)

    return df

# as always, let's put this in a function
def wdis_options_by_pos(roster, team_pos):
    is_wdis_elig = ((roster['player_position']
                    .astype(str)
                    .apply(lambda x: x in team_pos) & ~roster['start']) |
                    (roster['team_position'] == team_pos))

    return list(roster.loc[is_wdis_elig, 'fantasymath_id'])

def positions_from_roster(roster):
    return list(roster.loc[roster['start'] &
                           roster['fantasymath_id'].notnull(),
                           'team_position'])

if __name__ == '__main__':
    # open up our database connection
    conn = sqlite3.connect(DB_PATH)

    #######################################
    # load team and schedule data from DB
    #######################################

    teams = db.read_league('teams', LEAGUE_ID, conn)
    schedule = db.read_league('schedule', LEAGUE_ID, conn)
    league = db.read_league('league', LEAGUE_ID, conn)

    # get parameters from league DataFrame

    TEAM_ID = league.iloc[0]['team_id']
    HOST = league.iloc[0]['host']
    SCORING = {}
    SCORING['qb'] = league.iloc[0]['qb_scoring']
    SCORING['skill'] = league.iloc[0]['skill_scoring']
    SCORING['dst'] = league.iloc[0]['dst_scoring']

    #####################
    # get current rosters
    #####################

    # need players from FM API
    token = generate_token(LICENSE_KEY)['token']
    player_lookup = master_player_lookup(token).query("fleaflicker_id.notnull()")

    rosters = site.get_league_rosters(player_lookup, LEAGUE_ID, WEEK)

    ########################
    # what we need for wdis:
    ########################
    # 1. list of our starters

    roster = rosters.query(f"team_id == {TEAM_ID}")

    current_starters = list(roster.loc[roster['start'] &
                                       roster['fantasymath_id'].notnull(),
                                       'fantasymath_id'])

    # 2. list of opponent's starters

    # first: use schedule to find our opponent this week
    schedule_team = schedule_long(schedule)
    opponent_id = schedule_team.loc[
        (schedule_team['team_id'] == TEAM_ID) & (schedule_team['week'] == WEEK),
        'opp_id'].values[0]

    # then same thing
    opponent_starters = rosters.loc[
        (rosters['team_id'] == opponent_id) & rosters['start'] &
        rosters['fantasymath_id'].notnull(), ['fantasymath_id', 'actual']]


    # 3. sims
    available_players = get_players(token, **SCORING)

    players_to_sim = pd.concat([
        roster[['fantasymath_id', 'actual']],
        opponent_starters])

    sims = get_sims(token, set(players_to_sim['fantasymath_id']) &
                    set(available_players['fantasymath_id']),
                    nsims=1000, **SCORING)

    players_w_pts = players_to_sim.query("actual.notnull()")
    for player, pts in zip(players_w_pts['fantasymath_id'], players_w_pts['actual']):
        sims[player] = pts

    ################################################
    # analysis - call wdis_by_pos over all positions
    ################################################

    positions = positions_from_roster(roster)

    # calling actual analysis function goes here
    df_start = pd.concat(
        [wdis_by_pos(pos, sims, roster,
                     list(opponent_starters['fantasymath_id'])) for pos in
         positions])

    # extract starters
    rec_starters = [df_start.xs(pos)['wp'].idxmax() for pos in positions]

    ######################
    # write output to file
    ######################

    league_wk_output_dir = path.join(
        OUTPUT_PATH, f'{HOST}_{LEAGUE_ID}_2021-{str(WEEK).zfill(2)}')

    Path(league_wk_output_dir).mkdir(exist_ok=True)

    wdis_output_file = path.join(league_wk_output_dir, 'wdis.txt')

    with open(wdis_output_file, 'w') as f:
        print(f"WDIS Analysis, Fleaflicker League {LEAGUE_ID}, Week {WEEK}", file=f)
        print("", file=f)
        print(f"Run at {dt.datetime.now()}", file=f)
        print("", file=f)
        print("Recommended Starters:", file=f)
        for starter, pos in zip(rec_starters, positions):
            print(f"{pos}: {starter}", file=f)

        print("", file=f)
        print("Detailed Projections and Win Probability:", file=f)
        print(df_start[['mean', 'wp', 'wrong', 'regret']], file=f)
        print("", file=f)

        if set(current_starters) == set(rec_starters):
            print("Current starters maximize probability of winning.", file=f)
        else:
            print("Not maximizing probability of winning.", file=f)
            print("", file=f)
            print("Start:", file=f)
            print(set(rec_starters) - set(current_starters), file=f)
            print("", file=f)
            print("Instead of:", file=f)
            print(set(current_starters) - set(rec_starters), file=f)
