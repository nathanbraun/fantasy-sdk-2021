"""
v0.0.1
"""
import pandas as pd
from os import path
import matplotlib.pyplot as plt
import seaborn as sns
from textwrap import dedent
from pandas import DataFrame
from utilities import (get_sims, generate_token, LICENSE_KEY, LEAGUE_PATH)
from league_config import (SEASON, WEEK, SCORING, MATCHUPS,
                           WORKING_ROSTER_FILE, LEAGUE)

# NOTE: you shouldn't have to set any config options in this file
# instead do that in league_config.py

LEAGUE_OUTPUT = f'{LEAGUE}_analysis_{SEASON}-{str(WEEK).zfill(2)}.txt'

# put any players who've already played (e.g. in THU night game) here
SCORES = {
    # 'den-dst': 18
}

def lineup_by_owner(owner):
    return rosters.query(f"owner == '{owner}'")['fm_id']

def summarize_matchup(sims_a, sims_b):
    """
    Given two teams of sims (A and B), summarize a matchup with win
    probability, over-under, betting line, etc
    """

    # start by getting team totals
    total_a = sims_a.sum(axis=1)
    total_b = sims_b.sum(axis=1)

    # get win prob
    winprob_a = (total_a > total_b).mean().round(2)
    winprob_b = 1 - winprob_a.round(2)

    # get over-under
    over_under = (total_a + total_b).median().round(2)

    # line
    line = (total_a - total_b).median().round(2)
    line = round(line*2)/2

    return {'wp_a': winprob_a, 'wp_b': winprob_b, 'over_under': over_under,
            'line': line}

def lock_of_week(df):
    # team a
    wp_a = df[['team_a', 'wp_a', 'team_b']]
    wp_a.columns = ['team', 'wp', 'opp']

    # team b
    wp_b = df[['team_b', 'wp_b', 'team_a']]
    wp_b.columns = ['team', 'wp', 'opp']

    # combine
    stacked = pd.concat([wp_a, wp_b], ignore_index=True)

    # sort highest to low, pick out top
    lock = stacked.sort_values('wp', ascending=False).iloc[0]
    return lock.to_dict()

def photo_finish(df):
    # get the std dev of win probs, lowest will be cloest matchup
    wp_std = df[['wp_a', 'wp_b']].std(axis=1)

    # idxmin "index min" returns the index of the lowest value
    closest_matchup_id = wp_std.idxmin()

    return df.loc[closest_matchup_id].to_dict()

def summarize_team(sims):
    """
    Calculate summary stats on one set of teams.
    """
    totals = sims.sum(axis=1)
    # note: dropping count, min, max since those aren't that useful
    stats = (totals.describe(percentiles=[.05, .25, .5, .75, .95])
            [['mean', 'std', '5%', '25%', '50%', '75%', '95%']].to_dict())

    # maybe share of points by each pos? commented out now but could look if
    # interesting

    # stats['qb'] = sims.iloc[:,0].mean()
    # stats['rb'] = sims.iloc[:,1:3].sum(axis=1).mean()
    # stats['wr'] = sims.iloc[:,3:5].sum(axis=1).mean()
    # stats['te'] = sims.iloc[:,5].mean()
    # stats['k'] = sims.iloc[:,6].mean()
    # stats['dst'] = sims.iloc[:,7].mean()

    return stats

########################################################
# load weekly lineup, matchup info
# note: edit this if you want to analyze your own league
########################################################

if __name__ == '__main__':
    rosters = (pd.read_csv(path.join(LEAGUE_PATH, WORKING_ROSTER_FILE)))

    rosters = (pd.read_csv(path.join(LEAGUE_PATH,
                                     WORKING_ROSTER_FILE)).query("owner.notnull()"))

    token = generate_token(LICENSE_KEY)['token']

    sims = get_sims(token, list(rosters['fm_id']), nsims=1000, **SCORING)

    # update sims with SCORES
    for player, score in SCORES.items():
        sims[player] = score

    # apply summarize matchup to every matchup in the data
    matchup_list = []  # empty matchup list, where all our dicts will go

    for a, b in MATCHUPS:
        # gives us Series of starting lineups for each team in matchup
        lineup_a = rosters.query(f"owner == '{a}'")['fm_id']
        lineup_b = rosters.query(f"owner == '{b}'")['fm_id']

        # use lineups to grab right sims, feed into summarize_matchup function
        working_matchup_dict = summarize_matchup(
            sims[lineup_a], sims[lineup_b])

        # add some other info to working_matchup_dict
        working_matchup_dict['team_a'] = a
        working_matchup_dict['team_b'] = b

        # add working dict to list of matchups, then loop around to next
        # matchup
        matchup_list.append(working_matchup_dict)

    matchup_df = DataFrame(matchup_list)

    #################
    # analyzing teams
    #################

    team_list = []

    for team in rosters['owner'].unique():
        team_lineup = rosters.query(f"owner == '{team}'")['fm_id']
        working_team_dict = summarize_team(sims[team_lineup])
        working_team_dict['team'] = team

        team_list.append(working_team_dict)

    team_df = DataFrame(team_list).set_index('team')

    # high low
    # first step: get totals for each team in one DataFrame
    totals_by_team = pd.concat(
        [(sims[lineup_by_owner(owner)].sum(axis=1)
            .to_frame(owner)) for owner in rosters['owner'].unique()], axis=1)

    # then apply idxmax(axis=1) <- finds the name of column with the max, and
    # get % of time each team has the high in the sims
    team_df['p_high'] = (totals_by_team.idxmax(axis=1)
                        .value_counts(normalize=True))

    team_df['p_low'] = (totals_by_team.idxmin(axis=1)
                        .value_counts(normalize=True))

    # lets see what those high and lows are, on average
    # first step: get high score of every sim (max, not idxmax, we don't care
    # who got it)
    high_score = totals_by_team.max(axis=1)

    # same for low score
    low_score = totals_by_team.min(axis=1)

    # print results
    with open(path.join(LEAGUE_PATH, LEAGUE_OUTPUT), 'w') as f:
        print(dedent(
            f"""
            **********************************
            Matchup Projections, Week {WEEK} - {SEASON}
            **********************************
            """), file=f)
        print(matchup_df, file=f)

        print(dedent(
            f"""
            ********************************
            Team Projections, Week {WEEK} - {SEASON}
            ********************************
            """), file=f)

        print(team_df.round(2).sort_values('mean', ascending=False),
            file=f)

        print(dedent("""
              ************************
              High and Low Score Stats
              ************************
              """), file=f)
        print(pd.concat([
            high_score.describe(percentiles=[.05, .25, .5, .75, .95]),
            low_score.describe(percentiles=[.05, .25, .5, .75, .95])], axis=1),
            file=f)

        lock = lock_of_week(matchup_df)
        close = photo_finish(matchup_df)
        meh = matchup_df.sort_values('over_under').iloc[0]

        print(dedent("""
            Lock of the week:"""), file=f)
        print(f"{lock['team']} over {lock['opp']} — {lock['wp']}", file=f)

        print(dedent("""
                    Photo-finish of the week::"""), file=f)
        print(f"{close['team_a']} vs {close['team_b']}, {close['wp_a']}-{close['wp_b']}", file=f)

        print(dedent("""
                    Most unexciting game of the week:"""), file=f)
        print(f"{meh['team_a']} vs {meh['team_b']}, {meh['over_under']}", file=f)

    ################################################################################
    # plot section
    ################################################################################

    teams_long = totals_by_team.stack().reset_index()
    teams_long.columns = ['sim', 'team', 'pts']

    # plot
    g = sns.FacetGrid(teams_long, hue='team', aspect=2)
    g = g.map(sns.kdeplot, 'pts', shade=True)
    g.add_legend()
    g.fig.subplots_adjust(top=0.9)
    g.fig.suptitle(f'Team Points Distributions - Week {WEEK}')
    g.fig.savefig(path.join(LEAGUE_PATH, f'{LEAGUE}_{str(WEEK).zfill(2)}_team_dist.png'),
                bbox_inches='tight', dpi=500)

    # add in matchup info
    # add ID to each matchup tuple
    matchups_wid = [(a, b, f'{a} v {b}') for a, b in MATCHUPS]

    # reverse each matchup tuple, but keep same ID
    matchups_wid_reversed = [(b, a, i) for a, b, i in matchups_wid]

    # put into DataFrame
    matchup_lookup = DataFrame(matchups_wid + matchups_wid_reversed)
    matchup_lookup.columns = ['team', 'opp', 'matchup']

    # add to teams
    teams_long = pd.merge(teams_long, matchup_lookup[['team', 'matchup']])

    # and now we plot it
    g = sns.FacetGrid(teams_long, hue='team', col='matchup', col_wrap=2, aspect=2)
    g = g.map(sns.kdeplot, 'pts', shade=True)
    g.add_legend()
    g.fig.subplots_adjust(top=0.9)
    g.fig.suptitle(f'Team Distributions by matchup - Week {WEEK}')
    g.fig.savefig(path.join(LEAGUE_PATH, f'{LEAGUE}_{str(WEEK).zfill(2)}_team_dist_matchup.png'),
                bbox_inches='tight', dpi=500)


