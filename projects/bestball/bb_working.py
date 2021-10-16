import pandas as pd
from os import path
import seaborn as sns
from pandas import Series
from utilities import (get_players, get_sims, generate_token, LICENSE_KEY,
                       OUTPUT_PATH)

WEEK = 1
SEASON = 2019
SCORING = {'qb': 'pass4', 'skill': 'ppr', 'dst': 'mfl'}

roster = Series(['drew-brees', 'baker-mayfield', 'malcolm-brown',
                 'ezekiel-elliott', 'nyheim-hines', 'kareem-hunt',
                 'marlon-mack', 'devin-singletary', 'james-white',
                 'mike-evans', 'marquise-goodwin', 'mecole-hardman',
                 'christian-kirk', 'anthony-miller', 'dj-moore',
                 'curtis-samuel', 'noah-fant', 'george-kittle', 'cin-dst',
                 'den-dst']).to_frame('fantasymath_id')

token = generate_token(LICENSE_KEY)['token']
sims = get_sims(token, list(roster['fantasymath_id']), week=WEEK,
                season=SEASON, nsims=1000, **SCORING)

players = get_players(token, week=WEEK, season=SEASON, **SCORING)
roster = pd.merge(roster, players)
roster.head()

# players by pos
pos_dict = {pos: list(roster
                      .query(f"position == '{pos.upper()}'")['fantasymath_id']
                      .values) for pos in ['qb', 'rb', 'wr', 'te', 'dst']}

pos_dict

sims[pos_dict['qb']].max(axis=1).head()

sims[pos_dict['qb']].idxmax(axis=1).head()

# what about with 2 rbs
sim = sims.iloc[0]
sim

sim.loc[pos_dict['rb']]

sim.loc[pos_dict['rb']].sort_values(ascending=False).iloc[:2]

def n_highest_scores_from_sim1(sim, players, n):
    return sim.loc[players].sort_values(ascending=False).iloc[:n]

n_highest_scores_from_sim1(sim, pos_dict['rb'], 2)
n_highest_scores_from_sim1(sim, pos_dict['wr'], 3)

for i, row in sims.head().iterrows():
    print(i)
    print(row)

# apply this function on every sim for the first 5 rows
pd.concat([n_highest_scores_from_sim1(row, pos_dict['rb'], 2) for _, row
                in sims.head().iterrows()], ignore_index=True)

def n_highest_scores_from_sim(sim, players, n):
    # what we had before, but reset_index so we get the player too
    df = sim.loc[players].sort_values(ascending=False).iloc[:n].reset_index()
    df.columns = ['name', 'points']
    df['rank'] = range(1, n+1)
    df['sim'] = sim.name
    return df

n_highest_scores_from_sim(sim, pos_dict['rb'], 2)

# works for WRs too
n_highest_scores_from_sim(sim, pos_dict['wr'], 3)

rbs = pd.concat([n_highest_scores_from_sim(row, pos_dict['rb'], 2) for _, row
                 in sims.iterrows()], ignore_index=True)

rbs.head()

rbs_wide = rbs.set_index(['sim', 'rank']).unstack()
rbs_wide.head()

rbs_wide.columns = ['rb1_name', 'rb2_name', 'rb1_points', 'rb2_points']
rbs_wide.head()

points_from_rbs = rbs_wide[['rb1_points', 'rb2_points']].sum(axis=1)
points_from_rbs.mean()

rbs_wide['rb1_name'].value_counts(normalize=True)

def top_n_by_pos(sims, pos, players, n):
    df_long = pd.concat([n_highest_scores_from_sim(row, players, n) for
                        _, row in sims.iterrows()], ignore_index=True)
    df_wide = df_long.set_index(['sim', 'rank']).unstack()
    df_wide.columns = ([f'{pos}{x}_name' for x in range(1, n+1)] +
                    [f'{pos}{x}_points' for x in range(1, n+1)])
    return df_wide

# now can do with wr
wrs_wide = top_n_by_pos(sims, 'wr', pos_dict['wr'], 3)
wrs_wide.head()

# let's do it with other positions while we're at it
qb_wide = top_n_by_pos(sims, 'qb', pos_dict['qb'], 1)
te_wide = top_n_by_pos(sims, 'te', pos_dict['te'], 1)
dst_wide = top_n_by_pos(sims, 'dst', pos_dict['dst'], 1)

# now sum up points
proj_points = (
    qb_wide['qb1_points'] +
    te_wide['te1_points'] +
    dst_wide['dst1_points'] +
    rbs_wide[['rb1_points', 'rb2_points']].sum(axis=1) +
    wrs_wide[['wr1_points', 'wr2_points', 'wr3_points']].sum(axis=1))

# and analyze
proj_points.describe()

# after cutoff
def leftover_from_sim(sim, players, n):
    df = sim.loc[players].sort_values(ascending=False).iloc[n:].reset_index()
    df.columns = ['name', 'points']
    df['sim'] = sim.name
    return df

rbs_leftover = pd.concat([leftover_from_sim(row, pos_dict['rb'], 2) for _, row
                          in sims.iterrows()], ignore_index=True)
wrs_leftover = pd.concat([leftover_from_sim(row, pos_dict['wr'], 3) for _, row
                          in sims.iterrows()], ignore_index=True)
tes_leftover = pd.concat([leftover_from_sim(row, pos_dict['te'], 1) for _, row
                          in sims.iterrows()], ignore_index=True)

# combine them
leftovers = pd.concat([rbs_leftover, wrs_leftover, tes_leftover],
                      ignore_index=True)

leftovers.query("sim == 0")

# max by sim
leftovers.groupby('sim').max()['points'].head()

max_points_index = leftovers.groupby('sim').idxmax()['points']
max_points_index.head()

leftovers.loc[max_points_index].head()

# want to link that up with this:
qb_wide.head()

flex_wide = leftovers.loc[max_points_index].set_index('sim')
flex_wide.columns = ['flex_name', 'flex_points']

flex_wide.head()

# put everything together
team_wide = pd.concat([qb_wide, rbs_wide, wrs_wide, te_wide, flex_wide,
                       dst_wide], axis=1)

pos = ['qb', 'rb1', 'rb2', 'wr1', 'wr2', 'wr3', 'te', 'flex', 'dst']

names = team_wide[[x for x in team_wide.columns if x.endswith('_name')]]
names.columns = pos

points = team_wide[[x for x in team_wide.columns if x.endswith('_points')]]
points.columns = pos

names.head()
points.head()

points.sum(axis=1).describe(percentiles=[.05, .25, .5, .75, .95])

names['qb'].value_counts(normalize=True)
names['wr2'].value_counts(normalize=True)
names['flex'].value_counts(normalize=True)

usage = pd.concat([names[x].value_counts(normalize=True) for x in pos],
                  axis=1, join='outer').fillna(0)

usage.columns = [x.upper() for x in usage.columns]
usage['ALL'] = usage.sum(axis=1)

usage
usage_clean = usage.round(2).astype(str)

for x in usage_clean.columns:
    usage_clean[x] = usage_clean[x].str.pad(4, fillchar='0', side='right').str.replace('^0.00$','')

# print results
with open(path.join(OUTPUT_PATH, 'bestball', 'sample_bb_results.txt'), 'w') as f:
    print(points.sum(axis=1).describe(percentiles=[.05, .25, .5, .75, .95]),
          file=f)
    print(usage_clean, file=f)

######
# plot
######

players_long = sims[pos_dict['rb']].stack().reset_index()
players_long.columns = ['sim', 'player', 'points']

g = sns.FacetGrid(players_long, hue='player', aspect=2)
g = g.map(sns.kdeplot, 'points', shade=True)
g.add_legend()
g.fig.subplots_adjust(top=0.9)
g.fig.suptitle(f'RB Projections - Individual')
g.fig.savefig(path.join(OUTPUT_PATH, 'bestball', f'sample_bb_rb_{WEEK}.png'), bbox_inches='tight',
              dpi=500)

# add in best ball rbs
bb_rb_long = points[['rb1', 'rb2']].stack().reset_index()
bb_rb_long.columns = ['sim', 'player', 'points']

players_long = pd.concat([players_long, bb_rb_long], ignore_index=True)

# plot this again
g = sns.FacetGrid(players_long, hue='player', aspect=2)
g = g.map(sns.kdeplot, 'points', shade=True)
g.add_legend()
g.fig.subplots_adjust(top=0.9)
g.fig.suptitle(f'RB Projections - w/ Best Ball Starters')
g.fig.savefig(path.join(OUTPUT_PATH, 'bestball', f'sample_bb_rb_wstart_{WEEK}.png'),
              bbox_inches='tight', dpi=500)

