import os

import pandas as pd

try:
    from sqlalchemy import create_engine
except Exception:
    create_engine = None


TABLE_COLUMN_RENAMES = {
    'contract_snapshot': {
        'CYCLE_AKHIR': 'cycle',
        'CYCLE': 'cycle',
    },
}


def prepare_dataframe_for_table(table_name, df):
    """Normalize dataframe columns and a few values before DB insert."""
    prepared = df.copy()
    renames = TABLE_COLUMN_RENAMES.get(table_name, {})
    if renames:
        prepared = prepared.rename(columns=renames)

    prepared.columns = [str(column).lower() for column in prepared.columns]

    if 'promise_date' in prepared.columns:
        prepared['promise_date'] = prepared['promise_date'].replace('', None)

    return prepared


def create_postgres_engine_from_env():
    """Build a PostgreSQL SQLAlchemy engine from environment variables."""
    if create_engine is None:
        return None

    user = os.getenv('PGUSER', 'postgres')
    password = os.getenv('PGPASSWORD', '123123')
    host = os.getenv('PGHOST', 'localhost')
    port = os.getenv('PGPORT', '5432')
    database = os.getenv('PGDATABASE', 'collect_ai')

    engine_url = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
    return create_engine(engine_url)


def append_dataframes_to_postgres(dfs, if_exists='append'):
    """Append multiple dataframes into PostgreSQL tables."""
    engine = create_postgres_engine_from_env()
    if engine is None:
        print('sqlalchemy not installed; skipping DB write.')
        return

    for table_name, df in dfs.items():
        if df is None or df.empty:
            print(f'Skip empty dataframe for table {table_name}')
            continue

        prepared = prepare_dataframe_for_table(table_name, df)
        print(f'Writing {len(prepared)} rows to table {table_name} (if_exists={if_exists})')
        try:
            prepared.to_sql(
                table_name,
                con=engine,
                if_exists=if_exists,
                index=False,
                method='multi',
                chunksize=1000,
            )
        except Exception as exc:
            print(f'Failed to write table {table_name}: {exc}')
