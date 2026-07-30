import os

import pandas as pd

try:
    from sqlalchemy import create_engine, inspect, text
except Exception:
    create_engine = None
    inspect = None
    text = None

try:
    from dotenv import load_dotenv
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except Exception:
    pass


TABLE_COLUMN_RENAMES = {
    'contract_snapshot': {
        'CYCLE_AKHIR': 'cycle',
        'CYCLE': 'cycle',
    },
}

# Derived tables that reference contract_no/cust_id from the 4 source tables.
# Left populated after a --reset, they would reference stale IDs (the faker's
# PKs restart at 1) and reproduce exactly the inconsistent state a fresh demo
# is trying to avoid.
DERIVED_ML_TABLES = [
    'ai_intelligence_output',
    'customer_behavioral_standing',
    'scoring_feature_snapshot',
    'scoring_labels',
    'shadow_scores',
    'restructuring_recommendation_output',
    'restructuring_group_map',
    'restructuring_history',
    'restructuring_approval_log',
]


def prepare_dataframe_for_table(table_name, df, known_columns=None):
    """Normalize dataframe columns and a few values before DB insert."""
    prepared = df.copy()
    renames = TABLE_COLUMN_RENAMES.get(table_name, {})
    if renames:
        prepared = prepared.rename(columns=renames)

    prepared.columns = [str(column).lower() for column in prepared.columns]

    if 'promise_date' in prepared.columns:
        prepared['promise_date'] = prepared['promise_date'].replace('', None)

    if known_columns:
        extra = [c for c in prepared.columns if c not in known_columns]
        if extra:
            print(
                f"WARNING: table {table_name} does not have column(s) {extra} yet "
                f"(migration not applied?) — dropping from this load so it doesn't fail."
            )
            prepared = prepared.drop(columns=extra)

    return prepared


def create_postgres_engine_from_env():
    """Build a PostgreSQL SQLAlchemy engine from environment variables."""
    if create_engine is None:
        return None

    user = os.getenv('PGUSER', 'postgres')
    password = os.getenv('PGPASSWORD', '')
    host = os.getenv('PGHOST', 'localhost')
    port = os.getenv('PGPORT', '5432')
    database = os.getenv('PGDATABASE', 'collect_ai')

    engine_url = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'
    return create_engine(engine_url)


def _table_columns(engine, table_name):
    if inspect is None:
        return None
    try:
        insp = inspect(engine)
        if not insp.has_table(table_name):
            return None
        return {col['name'] for col in insp.get_columns(table_name)}
    except Exception:
        return None


def _table_row_count(engine, table_name):
    if text is None:
        return None
    try:
        with engine.connect() as conn:
            return conn.execute(text(f'SELECT count(*) FROM {table_name}')).scalar_one()
    except Exception:
        return None


def reset_tables(table_names, include_derived=True):
    """TRUNCATE the given tables (and, by default, the derived ML tables that
    reference them) before a re-run. Re-running the generator with the same
    seed produces the same deterministic PKs (CUST-00001, PAY-0000001, ...),
    so a plain append collides on the second run — this makes re-runs safe
    instead of relying on the swallowed-exception behavior this replaces."""
    engine = create_postgres_engine_from_env()
    if engine is None or text is None:
        print('sqlalchemy not installed; skipping reset.')
        return

    targets = list(table_names)
    if include_derived:
        targets = targets + DERIVED_ML_TABLES

    existing = [t for t in targets if _table_columns(engine, t) is not None]
    if not existing:
        return

    with engine.begin() as conn:
        conn.execute(text(f'TRUNCATE {", ".join(existing)} CASCADE'))
    print(f'Truncated: {", ".join(existing)}')


def append_dataframes_to_postgres(dfs, if_exists='append', require_empty=True):
    """Append multiple dataframes into PostgreSQL tables.

    If require_empty is True (the default when --reset was not passed), refuse
    to write into a table that already has rows, rather than attempting an
    append that would collide on the faker's deterministic primary keys and
    fail — this used to be swallowed by a bare `except Exception: print(...)`,
    which let a partially-loaded DB go unnoticed.
    """
    engine = create_postgres_engine_from_env()
    if engine is None:
        print('sqlalchemy not installed; skipping DB write.')
        return

    for table_name, df in dfs.items():
        if df is None or df.empty:
            print(f'Skip empty dataframe for table {table_name}')
            continue

        if require_empty:
            count = _table_row_count(engine, table_name)
            if count:
                raise RuntimeError(
                    f"Table {table_name} already has {count} rows. Re-running this generator "
                    f"reuses the same deterministic IDs (CUST-00001, PAY-0000001, ...), which "
                    f"would collide. Pass --reset to truncate first, or clear the DB manually."
                )

        known_columns = _table_columns(engine, table_name)
        prepared = prepare_dataframe_for_table(table_name, df, known_columns=known_columns)
        print(f'Writing {len(prepared)} rows to table {table_name} (if_exists={if_exists})')
        prepared.to_sql(
            table_name,
            con=engine,
            if_exists=if_exists,
            index=False,
            method='multi',
            chunksize=1000,
        )
