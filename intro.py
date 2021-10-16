import pandas as pd
from utilities import LICENSE_KEY, generate_token, get_players, get_sims

# parameters
SEASON = 2020
WEEK = 1
SCORING = {'qb': 'pass4', 'skill': 'ppr', 'dst': 'mfl'}

# get an access token
token = generate_token(LICENSE_KEY)['token']

# note: **SCORING same as passing qb='pass4', skill='ppr' ... to function
players = get_players(token, **SCORING, season=SEASON,
                      week=WEEK).set_index('fantasymath_id')

players.head()

# use this list of player ids (players.index) to get all the simulations for
# this week
sims = get_sims(token, players=list(players.index), week=WEEK, season=SEASON,
                nsims=1000, **SCORING)

sims.head()

sims.shape

sims['dak-prescott'].mean()
sims['dak-prescott'].median()

sims[['dak-prescott', 'russell-wilson']].head()

(sims['dak-prescott'] > sims['russell-wilson']).head()

(sims['dak-prescott'] > sims['russell-wilson']).mean()

(sims['dak-prescott'] >
         sims[['russell-wilson', 'baker-mayfield']].max(axis=1) + 11.5).mean()

sims['bb_qb'] = sims[['dak-prescott', 'russell-wilson']].max(axis=1)
sims[['bb_qb', 'dak-prescott', 'russell-wilson']].describe()

sims['bb_qb2'] = sims[['dak-prescott', 'russell-wilson',
                       'kirk-cousins']].max(axis=1)
sims[['bb_qb2', 'bb_qb', 'dak-prescott', 'russell-wilson',
      'kirk-cousins']].describe().round(2)

# correlations
sims[['aaron-rodgers', 'davante-adams']].corr()

sims[['aaron-rodgers', 'min-dst']].corr()

sims[['aaron-rodgers', 'davante-adams', 'min-dst']].corr()
sims[['aaron-rodgers', 'davante-adams', 'kirk-cousins', 'tom-brady', 'min-dst']].corr().round(2)

sims['davante-adams'].describe()

pd.concat([
    sims.loc[sims['aaron-rodgers'] > 30, 'davante-adams'].describe(),
    sims.loc[sims['aaron-rodgers'] < 12, 'davante-adams'].describe()], axis=1)

(sims['matt-ryan'] > sims['dak-prescott']).mean()

(sims[['matt-ryan', 'julio-jones']].sum(axis=1) > 60).mean()

(sims[['dak-prescott', 'julio-jones']].sum(axis=1) > 60).mean()
