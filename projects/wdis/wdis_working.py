import pandas as pd
from os import path
import seaborn as sns
from pandas import Series
from utilities import (generate_token, get_sims, LICENSE_KEY, get_players,
                       OUTPUT_PATH)

# generate access token
token = generate_token(LICENSE_KEY)['token']

WEEK = 1
SEASON = 2019
NSIMS = 1000
SCORING = {'qb': 'pass6', 'skill': 'ppr', 'dst': 'high'}

team1 = ['drew-brees', 'alvin-kamara', 'sony-michel', 'julio-jones',
        'keenan-allen', 'jared-cook', 'matt-prater', 'lar-dst']

team2 = ['russell-wilson', 'christian-mccaffrey', 'saquon-barkley',
         'corey-davis', 'dante-pettis', 'greg-olsen', 'matt-gay',
         'buf-dst']

bench = ['lesean-mccoy', 'phillip-lindsay', 'royce-freeman']


valid_players = get_players(token, season=SEASON, week=WEEK, **SCORING)

list(valid_players['fantasymath_id'])[:20]

# and query sims
players = team1 + team2 + bench
sims = get_sims(token, players, week=WEEK, season=SEASON, nsims=NSIMS,
                **SCORING)

sims.head()

# coding up WDIS
sims[team1].head()

sims[team1].sum()

sims[team1].sum(axis=1).head()
sims[team2].sum(axis=1).head()

team1_beats_team2 = sims[team1].sum(axis=1) > sims[team2].sum(axis=1)
team1_beats_team2.head()

team1_beats_team2.mean()

# first cut at WDIS
def simple_wdis(sims, team1, team2, wdis):
    team1_wdis = team1 + [wdis]
    return (sims[team1_wdis].sum(axis=1) > sims[team2].sum(axis=1)).mean()

team1_no_wdis = ['drew-brees', 'alvin-kamara', 'julio-jones', 'keenan-allen',
                 'jared-cook', 'matt-prater', 'lar-dst']

wdis = ['sony-michel', 'lesean-mccoy', 'phillip-lindsay', 'royce-freeman']

for player in wdis:
    print(player)
    print(simple_wdis(sims, team1_no_wdis, team2, player))

# modify it to so it takes in a list of wdis players and analyzes them all
def simple_wdis2(sims, team1, team2, wdis):
    return {
        player: (sims[team1 + [player]].sum(axis=1) >
                 sims[team2].sum(axis=1)).mean()
        for player in wdis}

simple_wdis2(sims, team1_no_wdis, team2, wdis)

# modify so can take a complete team1
def simple_wdis3(sims, team1, team2, wdis):

    # there should be one player that overlaps in wdis and team1
    team1_no_wdis = [x for x in team1 if x not in wdis]

    # another way to do this is using python sets
    # team1_no_wdis_alt = set(team1) - set(wdis)

    return {
        player: (sims[team1_no_wdis + [player]].sum(axis=1) >
                 sims[team2].sum(axis=1)).mean() for player in wdis}

simple_wdis2(sims, team1_no_wdis, team2, wdis)
simple_wdis3(sims, team1, team2, wdis)
simple_wdis3(sims, team1, team2, ['matt-prater', 'matt-gay'])

# throws an error
# assert False

# no error
assert True

def simple_wdis4(sims, team1, team2, wdis):

    # there should be one player that overlaps in wdis and team1
    team1_no_wdis = [x for x in team1 if x not in wdis]

    # some checks
    current_starter = [x for x in team1 if x in wdis]
    assert len(current_starter) == 1

    bench_options = [x for x in wdis if x not in team1]
    assert len(bench_options) >= 1

    return Series({
        player: (sims[team1_no_wdis + [player]].sum(axis=1) >
                 sims[team2].sum(axis=1)).mean() for player in wdis}).sort_values(ascending=False)


simple_wdis4(sims, team1, team2, wdis)

# here's where we landed
team1 = ['drew-brees', 'alvin-kamara', 'sony-michel', 'julio-jones',
        'keenan-allen', 'jared-cook', 'matt-prater', 'lar-dst']

team2 = ['russell-wilson', 'christian-mccaffrey', 'saquon-barkley',
         'corey-davis', 'dante-pettis', 'greg-olsen', 'matt-gay',
         'buf-dst']

current_starter = 'sony-michel'
bench_options = ['lesean-mccoy', 'phillip-lindsay', 'royce-freeman']
team1_sans_starter = [x for x in team1 if (x != current_starter) and x not in
                      bench_options]

# overall score
sims[team1].sum(axis=1).describe()

stats = pd.concat([(sims[team1_sans_starter].sum(axis=1) + sims[x]).describe()
                   for x in wdis], axis=1)
stats.columns = wdis  # make column names = players
stats

stats.T.drop(['count', 'min', 'max'], axis=1)  # drop unnec columns

# prob of starting the wrong guy
sims[bench_options].max(axis=1).head()

(sims[bench_options].max(axis=1) > sims[current_starter]).mean()

# prob of losing because we start the wrong guy
# pieces we need
team1_w_starter = sims[team1_sans_starter].sum(axis=1) + sims[current_starter]

team1_w_best_backup = (sims[team1_sans_starter].sum(axis=1) +
                      sims[bench_options].max(axis=1))

team2_total = sims[team2].sum(axis=1)

# true if team w/ best backup > team2 AND team w/ starer we picked < team2
regret_col = ((team1_w_best_backup > team2_total) &
              (team1_w_starter < team2_total))
regret_col.mean()

# function forms
def sumstats(starter):
    team_w_starter = sims[team1_sans_starter].sum(axis=1) + sims[starter]
    stats_series = (team_w_starter
                    .describe(percentiles=[.05, .25, .5, .75, .95])
                    .drop(['count', 'min', 'max']))
    stats_series.name = starter
    return stats_series

def win_prob(starter):
    team_w_starter = sims[team1_sans_starter].sum(axis=1) + sims[starter]
    return (team_w_starter > team2_total).mean()

def wrong_prob(starter, bench):
    return (sims[bench].max(axis=1) > sims[starter]).mean()

def regret_prob(starter, bench):
    team_w_starter = sims[team1_sans_starter].sum(axis=1) + sims[starter]
    team_w_best_backup = (sims[team1_sans_starter].sum(axis=1) +
                        sims[bench].max(axis=1))

    return ((team_w_best_backup > team2_total) &
            (team_w_starter < team2_total)).mean()

win_prob(current_starter)
wrong_prob(current_starter, bench_options)
regret_prob(current_starter, bench_options)

# now with next best alternative, lindsay
sumstats('phillip-lindsay')
win_prob('phillip-lindsay')
wrong_prob('phillip-lindsay',
           ['lesean-mccoy', 'sony-michel', 'royce-freeman'])
regret_prob('phillip-lindsay',
            ['lesean-mccoy', 'sony-michel', 'royce-freeman'])

# and so on ...

def start_bench_scenarios(wdis):
    """
    Return all combinations of start, backups for all players in wdis.
    """
    return [{
        'starter': player,
        'bench': [x for x in wdis if x != player]
    } for player in wdis]


scenarios = start_bench_scenarios(wdis)

# simpler start bench scenarios
wdis

# concrete case
player = 'sony-michel'
[x for x in wdis if x != player]

# want that in a dict:
{'starter': player, 'bench': [x for x in wdis if x != player]}

# start with table of sum stats
df = pd.concat([sumstats(player) for player in wdis], axis=1)

df = df.T

# now let's go through and add all our extra data to it
# start with win prob
wps = [win_prob(player) for player in wdis]
df['wp'] = wps  # adding wps as a column to our data of stats

df.head()

# now do wrong prob
# note, skipping separate step above and just putting it in the dataframe all
# at once
df['wrong'] = [wrong_prob(scen['starter'], scen['bench']) for scen in scenarios]

# now regret prob
# this time: ** trick, can p
df['regret'] = [regret_prob(**scen) for scen in scenarios]

# final result:
df

def wdis_plus(sims, team1, team2, wdis):

    # do some validity checks
    current_starter = set(team1) & set(wdis)
    assert len(current_starter) == 1

    bench_options = set(wdis) - set(team1)
    assert len(bench_options) >= 1

    team_sans_starter = list(set(team1) - current_starter)

    scenarios = start_bench_scenarios(wdis)
    team2_total = sims[team2].sum(axis=1)  # opp

    # note these functions all work with sims, even though they don't take sims
    # as an argument
    # it works because everything inside wdis_plus has access to sims
    # if these functions were defined outside of wdis_plus it wouldn't work
    # this is an example of lexical scope: https://stackoverflow.com/a/53062093
    def sumstats(starter):
        team_w_starter = sims[team_sans_starter].sum(axis=1) + sims[starter]
        team_info = (team_w_starter
                    .describe(percentiles=[.05, .25, .5, .75, .95])
                    .drop(['count', 'min', 'max']))

        return team_info

    def win_prob(starter):
        team_w_starter = sims[team_sans_starter].sum(axis=1) + sims[starter]
        return (team_w_starter > team2_total).mean()

    def wrong_prob(starter, bench):
        return (sims[bench].max(axis=1) > sims[starter]).mean()

    def regret_prob(starter, bench):
        team_w_starter = sims[team_sans_starter].sum(axis=1) + sims[starter]
        team_w_best_backup = (sims[team_sans_starter].sum(axis=1) +
                            sims[bench].max(axis=1))

        return ((team_w_best_backup > team2_total) &
                (team_w_starter < team2_total)).mean()


    # start with DataFrame of summary stats
    df = pd.concat([sumstats(player) for player in wdis], axis=1)
    df.columns = wdis
    df = df.T

    # then add prob of win, being wrong, regretting decision
    df['wp'] = [win_prob(x['starter']) for x in scenarios]
    df['wrong'] = [wrong_prob(**x) for x in scenarios]
    df['regret'] = [regret_prob(**x) for x in scenarios]

    return df.sort_values('wp', ascending=False)


wdis_plus(sims, team1, team2, wdis)

# now lets use our new function to analyze every kicker on waivers

fa_kickers = ['aldrick-rosas', 'austin-seibert', 'cairo-santos',
              'zane-gonzalez', 'chris-boswell', 'kaare-vedvik',
              'eddy-pineiro', 'daniel-carlson', 'dustin-hopkins']

k_sims = get_sims(token, fa_kickers, week=WEEK, season=SEASON, nsims=1000,
                      **SCORING)

sims_plus = pd.concat([sims, k_sims], axis=1)

wdis_k = fa_kickers + ['matt-prater']

df_k = wdis_plus(sims_plus, team1, team2, wdis_k)

############################
# now let's do some plotting
############################

points_wide = pd.concat(
    [sims[team1].sum(axis=1), sims[team2].sum(axis=1)], axis=1)
points_wide.columns = ['team1', 'team2']
points_wide.head()

points_wide.stack().head()

points_long = points_wide.stack().reset_index()
points_long.columns = ['sim', 'team', 'points']
points_long.head()

g = sns.FacetGrid(points_long, hue='team', aspect=2)
g = g.map(sns.kdeplot, 'points', shade=True)
g.add_legend()
g.fig.subplots_adjust(top=0.9)
g.fig.suptitle('Team Fantasy Points Distributions')
g.fig.savefig(path.join(OUTPUT_PATH, 'wdis', 'wdis_dist_by_team1.png'),
              bbox_inches='tight', dpi=500)


# all players

current_starter = 'sony-michel'
bench_options = ['lesean-mccoy', 'phillip-lindsay', 'royce-freeman']
team1_sans_starter = [x for x in team1 if (x != current_starter) and x not in
                      bench_options]

points_wide = pd.concat(
    [sims[team1_sans_starter].sum(axis=1) + sims[player] for player in wdis], axis=1)
points_wide.columns = wdis
points_wide['opp'] = sims[team2].sum(axis=1)

points_wide.head()

# rest is the same as above
points_long = points_wide.stack().reset_index()
points_long.columns = ['sim', 'team', 'points']

points_long.head()

g = sns.FacetGrid(points_long, hue='team', aspect=2)
g = g.map(sns.kdeplot, 'points', shade=True)
g.add_legend()
g.fig.subplots_adjust(top=0.9)
g.fig.suptitle('Team Fantasy Points Distributions - WDIS Options')
g.fig.savefig(path.join(OUTPUT_PATH,'wdis', 'wdis_dist_by_team2.png'),
              bbox_inches='tight', dpi=500)

def wdis_plot(sims, team1, team2, wdis):

    # do some validity checks
    current_starter = set(team1) & set(wdis)
    assert len(current_starter) == 1

    bench_options = set(wdis) - set(team1)
    assert len(bench_options) >= 1

    #
    team_sans_starter = list(set(team1) - current_starter)

    # total team points under allt he starters
    points_wide = pd.concat(
        [sims[team_sans_starter].sum(axis=1) + sims[player] for player in
         wdis], axis=1)

    points_wide.columns = wdis

    # add in apponent
    points_wide['opp'] = sims[team2].sum(axis=1)

    # shift data from columns to rows to work with seaborn
    points_long = points_wide.stack().reset_index()
    points_long.columns = ['sim', 'team', 'points']

    # actual plotting portion
    g = sns.FacetGrid(points_long, hue='team', aspect=4)
    g = g.map(sns.kdeplot, 'points', shade=True)
    g.add_legend()
    g.fig.subplots_adjust(top=0.9)
    g.fig.suptitle('Team Fantasy Points Distributions - WDIS Options')

    return g


# individual player plots

pw = sims[wdis].stack().reset_index()
pw.columns = ['sim', 'player', 'points']

g = sns.FacetGrid(pw, hue='player', aspect=2)
g = g.map(sns.kdeplot, 'points', shade=True)
g.add_legend()
g.fig.subplots_adjust(top=0.9)
g.fig.suptitle(f'WDIS Projections')
g.fig.savefig(path.join(OUTPUT_PATH, 'wdis', f'player_wdis_dist_{WEEK}.png'),
              bbox_inches='tight', dpi=500)
