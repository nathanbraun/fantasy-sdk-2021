import pandas as pd
from textwrap import dedent

def _clear_league_from_table(league_id, table, conn):
    tables_in_db = [x[0] for x in list(conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"))]

    if table in tables_in_db:
        conn.execute(dedent(f"""
            DELETE FROM {table}
            WHERE league_id = {league_id};"""))

def overwrite_league(df, name, conn, league_id):
    _clear_league_from_table(league_id, name, conn)
    df.to_sql(name, conn, index=False, if_exists='append')


def read_league(name, league_id, conn):
    return pd.read_sql(dedent(
        f"""
        SELECT *
        FROM {name}
        WHERE league_id = {league_id}
        """), conn)
