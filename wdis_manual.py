import pandas as pd
from os import path
import seaborn as sns
from utilities import generate_token, get_sims, LICENSE_KEY, OUTPUT_PATH

WEEK = 1
SEASON = 2019
NSIMS = 1000
SCORING = {'qb': 'pass6', 'skill': 'ppr', 'dst': 'high'}

team1 = ['drew-brees', 'alvin-kamara', 'sony-michel', 'julio-jones',
        'keenan-allen', 'jared-cook', 'matt-prater', 'lar-dst']

team2 = ['russell-wilson', 'christian-mccaffrey', 'saquon-barkley',
            'corey-davis', 'dante-pettis', 'greg-olsen', 'matt-gay',
            'buf-dst']

wdis = ['sony-michel', 'lesean-mccoy', 'phillip-lindsay', 'royce-freeman']

def start_bench_scenarios(wdis):
    """
    Return all combinations of start, backups for all players in wdis.
    """
    return [{
        'starter': player,
        'bench': [x for x in wdis if x != player]
    } for player in wdis]

def calculate(sims, team1, team2, wdis):

    # do some validity checks
    current_starter = set(team1) & set(wdis)
    assert len(current_starter) == 1

    # bench_options = set(wdis) - set(team1)
    # if len(bench_options) >= 0:
    #     print("warning - no bench options")

    wdis = list(set(wdis) & set(sims.columns))

    team_sans_starter = list(set(team1) - current_starter)

    scenarios = start_bench_scenarios(wdis)
    team2_total = sims[team2].sum(axis=1)  # opp

    # note these functions all work with sims, even though they don't take sims
    # as an argument
    # it works because everything inside calculate has access to sims
    # if these functions were defined outside of calculate it wouldn't work
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

def plot(sims, team1, team2, wdis):

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

if __name__ == '__main__':

    # generate access token
    token = generate_token(LICENSE_KEY)['token']

    players = list(set(team1) | set(team2) | set(wdis))

    sims = get_sims(token, players, week=WEEK, season=SEASON, nsims=NSIMS,
                        **SCORING)

    df = calculate(sims, team1, team2, wdis)

    g = plot(sims, team1, team2, wdis)

    g.fig.savefig(path.join(OUTPUT_PATH, 'wdis_dist_by_team.png'),
                bbox_inches='tight', dpi=500)

    # plot wdis players
    pw = sims[wdis].stack().reset_index()
    pw.columns = ['sim', 'player', 'points']

    g = sns.FacetGrid(pw, hue='player', aspect=2)
    g = g.map(sns.kdeplot, 'points', shade=True)
    g.add_legend()
    g.fig.subplots_adjust(top=0.9)
    g.fig.suptitle(f'WDIS Projections')
    g.fig.savefig(path.join(WDIS_PATH, f'player_wdis_dist_{WEEK}.png'),
                bbox_inches='tight', dpi=500)
