import pandas as pd
from os import path
from pandas import Series
from utilities import (get_players, get_sims, generate_token, LICENSE_KEY,
                       OUTPUT_PATH)

# PARAMETERS
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

def n_highest_scores_from_sim(sim, players, n):
    df = sim.loc[players].sort_values(ascending=False).iloc[:n].reset_index()
    df.columns = ['name', 'points']
    df['rank'] = range(1, n+1)
    df['sim'] = sim.name
    return df

def top_n_by_pos(sims, pos, players, n):
    df_long = pd.concat([n_highest_scores_from_sim(row, players, n) for
                        _, row in sims.iterrows()], ignore_index=True)
    df_wide = df_long.set_index(['sim', 'rank']).unstack()
    df_wide.columns = ([f'{pos}{x}_name' for x in range(1, n+1)] +
                    [f'{pos}{x}_points' for x in range(1, n+1)])
    return df_wide

# after cutoff
def leftover_from_sim(sim, players, n):
    df = sim.loc[players].sort_values(ascending=False).iloc[n:].reset_index()
    df.columns = ['name', 'points']
    df['sim'] = sim.name
    return df

if __name__ == '__main__':
    # get auth token
    token = generate_token(LICENSE_KEY)['token']

    # query players from API and add in position to roster
    players = get_players(token, week=WEEK, season=SEASON, **SCORING)

    # commented out, but use this function for current week in 2020 season
    # (will also have to change roster variable above)

    # players = get_players(token, **SCORING)

    roster = pd.merge(roster, players)

    # need dict of rosters by pos, list of players
    pos_dict = {pos.lower(): list(roster.query(f"position == '{pos}'")['fantasymath_id'].values) for
                pos in ['QB', 'RB', 'WR', 'TE', 'DST']}

    # query sims from API
    sims = get_sims(token, list(roster['fantasymath_id']), week=WEEK, season=SEASON,
                    nsims=1000, **SCORING)

    # get top N players by each position — not flex
    qb_wide = top_n_by_pos(sims, 'qb', pos_dict['qb'], 1)
    rbs_wide = top_n_by_pos(sims, 'rb', pos_dict['rb'], 2)
    wrs_wide = top_n_by_pos(sims, 'wr', pos_dict['wr'], 3)
    te_wide = top_n_by_pos(sims, 'te', pos_dict['te'], 1)
    dst_wide = top_n_by_pos(sims, 'dst', pos_dict['dst'], 1)

    # flex section
    # not get N + 1 to the end players for RB/WR/TE for flex
    rbs_leftover = pd.concat([leftover_from_sim(row, pos_dict['rb'], 2) for _, row
                            in sims.iterrows()], ignore_index=True)
    wrs_leftover = pd.concat([leftover_from_sim(row, pos_dict['wr'], 3) for _, row
                            in sims.iterrows()], ignore_index=True)
    tes_leftover = pd.concat([leftover_from_sim(row, pos_dict['te'], 1) for _, row
                            in sims.iterrows()], ignore_index=True)

    # stick leftovers together
    leftovers = pd.concat([rbs_leftover, wrs_leftover, tes_leftover],
                        ignore_index=True)

    # and find best leftover/flex player
    max_points_index = leftovers.groupby('sim').idxmax()['points']

    flex_wide = leftovers.loc[max_points_index].set_index('sim')
    flex_wide.columns = ['flex_name', 'flex_points']

    # combine flex and non flex
    team_wide = pd.concat([qb_wide, rbs_wide, wrs_wide, te_wide, flex_wide,
                        dst_wide], axis=1)

    # have what we want, now put into two DataFrames (names and points) to
    # simplify analysis
    pos = ['qb', 'rb1', 'rb2', 'wr1', 'wr2', 'wr3', 'te', 'flex', 'dst']

    names = team_wide[[x for x in team_wide.columns if x.endswith('_name')]]
    names.columns = pos

    points = team_wide[[x for x in team_wide.columns if x.endswith('_points')]]
    points.columns = pos

    # final summary:
    usage = pd.concat([names[x].value_counts(normalize=True) for x in pos],
                    axis=1, join='outer').fillna(0)

    # clean this up and get rid of 0s
    usage.columns = [x.upper() for x in usage.columns]
    usage['ALL'] = usage.sum(axis=1)

    usage_clean = usage.round(2).astype(str)

    for x in usage_clean.columns:
        usage_clean[x] = usage_clean[x].str.pad(4, fillchar='0', side='right').str.replace('^0.00$','')

    # output final results results
    with open(path.join(OUTPUT_PATH, 'bestball', 'bb_results.txt'), 'w') as f:
        print("Projected Score w/ Percentiles:")
        print(points.sum(axis=1).describe(percentiles=[.05, .25, .5, .75, .95]),
            file=f)
        print("Projected Usage:")
        print(usage_clean, file=f)
