import hosts.fleaflicker as site
import hosts.db as db
import datetime as dt
from textwrap import dedent
from pandas import DataFrame, Series
import sqlite3
import wdis
import pandas as pd
from utilities import (LICENSE_KEY, generate_token, master_player_lookup,
                       get_sims, get_players, DB_PATH, OUTPUT_PATH)

LEAGUE_ID = 316893
WEEK = 2

# open up our database connection
conn = sqlite3.connect(DB_PATH)

#######################################
# load team and schedule data from DB
#######################################

###############################################################################
# normally: run this - AFTER you've run ./hosts/league_setup.py w/ your league
###############################################################################

# teams = db.read_league('teams', LEAGUE_ID, conn)
# schedule = db.read_league('schedule', LEAGUE_ID, conn)
# league = db.read_league('league', LEAGUE_ID, conn)
# host = league.iloc[0]['host']

###############################################################################
# but for this example, using outputs i've saved here
###############################################################################

teams = pd.read_csv('./projects/integration/raw/wdis/teams.csv')
schedule = pd.read_csv('./projects/integration/raw/wdis/schedule.csv')
league = pd.read_csv('./projects/integration/raw/wdis/league.csv')
host = league.iloc[0]['host']

# get parameters from league DataFrame

TEAM_ID = league.iloc[0]['team_id']
SCORING = {}
SCORING['qb'] = league.iloc[0]['qb_scoring']
SCORING['skill'] = league.iloc[0]['skill_scoring']
SCORING['dst'] = league.iloc[0]['dst_scoring']

################################
# get current rosters + starters
################################

# need players from FM API
token = generate_token(LICENSE_KEY)['token']
player_lookup = master_player_lookup(token).query("fleaflicker_id.notnull()")

player_lookup = pd.read_csv('./projects/integration/raw/wdis/player_lookup.csv')

# rosters = site.get_league_rosters(player_lookup, LEAGUE_ID, WEEK)
rosters = pd.read_csv('./projects/integration/raw/wdis/rosters.csv')

# what we need for wdis:
# list of our starters

roster = rosters.query(f"team_id == {TEAM_ID}")
roster.head()

current_starters = list(roster.loc[roster['start'] &
                                   roster['fantasymath_id'].notnull(),
                                   'fantasymath_id'])

current_starters

def schedule_long(sched):
    sched1 = schedule.rename(columns={'team1_id': 'team_id', 'team2_id':
                                      'opp_id'})
    sched2 = schedule.rename(columns={'team2_id': 'team_id', 'team1_id':
                                      'opp_id'})
    return pd.concat([sched1, sched2], ignore_index=True)

schedule_team = schedule_long(schedule)

opponent_id = schedule_team.loc[
    (schedule_team['team_id'] == TEAM_ID) & (schedule_team['week'] == WEEK),
    'opp_id'].values[0]

# then same thing
opponent_starters = rosters.loc[
    (rosters['team_id'] == opponent_id) & rosters['start'] &
    rosters['fantasymath_id'].notnull(), ['fantasymath_id', 'actual']]

opponent_starters

players_to_sim = pd.concat([
    roster[['fantasymath_id', 'actual']],
    opponent_starters])

# sims
# available_players = get_players(token, season=2021, week=WEEK, **SCORING)
available_players = pd.read_csv('./projects/integration/raw/wdis/available_players.csv')

# now get sims
# easiest to just get sims for every player on our team

sims = get_sims(token, set(players_to_sim['fantasymath_id'])  &
                set(available_players['fantasymath_id']), season=2021,
                week=WEEK, nsims=1000, **SCORING)

players_w_pts = players_to_sim.query("actual.notnull()")
for player, pts in zip(players_w_pts['fantasymath_id'], players_w_pts['actual']):
    sims[player] = pts

# wdis options + current starter
wdis_options = ['antonio-brown', 'jaylen-waddle', 'christian-kirk']

wdis.calculate(sims, current_starters, opponent_starters['fantasymath_id'],
               wdis_options)

wdis.calculate(sims, current_starters, opponent_starters['fantasymath_id'],
               ['jalen-hurts', 'mac-jones'])

# cool, still annoying to manipulate wdis options

# lets write some code that takes our roster, a *position* and calculates
# probability of winning with starter + eligible bench players

# only "tricky" thing is getting a list of the bench + current starters to run
# through wdis.calculate function

# start out with specific example
pos = 'WR1'

# way to do it: player_position in 'WR1'
# true for WR, not true for RB

'WR' in 'WR1'
'RB' in 'WR1'

'WR' in 'RB/WR/TE'
'QB' in 'RB/WR/TE'

'RB' in 'FLEX'

# no built in pandas function, so use apply

# throws an error
# roster['player_position'].apply(lambda x: x in pos)

pos_in_wr1 = roster['player_position'].astype(str).apply(lambda x: x in pos)
pos_in_wr1

# col of bools, plug it into loc[] to see who we're dealing with
roster.loc[pos_in_wr1]

# almost right, but we don't want ALL WRs, just bench options + candidate
# currently in WR1 spot
bench_wr1_elig = ((roster['player_position']
                   .astype(str)
                   .apply(lambda x: x in pos) & ~roster['start']) |
                  (roster['team_position'] == pos))

wdis_ids = list(roster.loc[bench_wr1_elig, 'fantasymath_id'])
wdis_ids

wdis.calculate(sims, current_starters, opponent_starters['fantasymath_id'], wdis_ids)

# as always, let's put this in a function
def wdis_options_by_pos(roster, team_pos):
    is_wdis_elig = ((roster['player_position']
                    .astype(str)
                    .apply(lambda x: x in team_pos) & ~roster['start']) |
                    (roster['team_position'] == team_pos))

    return list(roster.loc[is_wdis_elig, 'fantasymath_id'])

wdis_players_flex = wdis_options_by_pos(roster, 'RB/WR/TE')
wdis_players_flex

# easy to plug into calculate
df_flex = wdis.calculate(sims, current_starters,
                         opponent_starters['fantasymath_id'],
                         wdis_players_flex)

df_flex

# nwo put all this in a function
def wdis_by_pos1(pos, sims, roster, opp_starters):
    wdis_options = wdis_options_by_pos(roster, pos)

    starters = list(roster.loc[
        rosters['start'] &
        rosters['fantasymath_id'].notnull(), 'fantasymath_id'])

    return wdis.calculate(sims, starters, opp_starters,
                          set(wdis_options) & set(sims.columns))

wdis_by_pos1('QB', sims, roster, opponent_starters['fantasymath_id'])
wdis_by_pos1('RB/WR/TE', sims, roster, opponent_starters['fantasymath_id'])

positions = list(roster.loc[roster['start'] & roster['fantasymath_id'].notnull(), 'team_position'])
positions

def positions_from_roster(roster):
    return list(roster.loc[roster['start'] &
                           roster['fantasymath_id'].notnull(),
                           'team_position'])

positions_from_roster(roster)

for pos in positions:
    print(wdis_by_pos1(pos, sims, roster, opponent_starters))

# cool to add name of player to start
def wdis_by_pos2(pos, sims, roster, opp_starters):
    wdis_options = wdis_options_by_pos(roster, pos)

    starters = list(roster.loc[
        rosters['start'] &
        rosters['fantasymath_id'].notnull(), 'fantasymath_id'])

    df = wdis.calculate(sims, starters, opp_starters,
                        set(wdis_options) & set(sims.columns))

    rec_start_id = df['wp'].idxmax()

    df['pos'] = pos
    df.index.name = 'player'
    df.reset_index(inplace=True)
    df.set_index(['pos', 'player'], inplace=True)

    return df

wdis_by_pos2('QB', sims, roster, opponent_starters['fantasymath_id'])

df_start = pd.concat(
    [wdis_by_pos2(pos, sims, roster, opponent_starters['fantasymath_id']) for
     pos in positions])

df_start.head(10)

df_start.xs('WR1')
df_start.xs('WR1')['wp'].idxmax()

rec_starters = [df_start.xs(pos)['wp'].idxmax() for pos in positions]
rec_starters

positions

for pos, starter in zip(positions, rec_starters):
    print(f"at {pos}, start {starter}")

# writing to a file
my_file = open('league_info.txt', 'w')
print(f"Your league is {LEAGUE_ID}!", file=my_file)

print(f'WDIS Analysis, Fleaflicker League {LEAGUE_ID}, Week {WEEK}',
      file=my_file)

# writing output ot a file
f'fleaflicker_{LEAGUE_ID}_2021-{str(WEEK).zfill(2)}-wdis.txt'

f'./output/fleaflicker_{LEAGUE_ID}_2021-{str(WEEK).zfill(2)}/wdis.txt'

from pathlib import Path
from os import path

league_wk_output_dir = path.join(
    OUTPUT_PATH, f'{host}_{LEAGUE_ID}_2021-{str(WEEK).zfill(2)}')

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
