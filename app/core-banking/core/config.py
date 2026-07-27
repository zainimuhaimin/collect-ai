"""Konfigurasi app/core-banking/ — simulasi sistem loan origination/core
banking terpisah dari collect-ai (ML + backend). Kredensial dari .env yang
SAMA dipakai app/backend/ dan app/machine-learning/ (satu Postgres, satu
sumber kredensial) — lihat .env.example di root repo."""
from __future__ import annotations

import os

from dotenv import load_dotenv

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

if os.environ.get("COLLECTAI_DB_URL"):
    DB_URL = os.environ["COLLECTAI_DB_URL"]
else:
    _pg_host = os.environ.get("PGHOST", "localhost")
    _pg_port = os.environ.get("PGPORT", "5432")
    _pg_user = os.environ.get("PGUSER", "postgres")
    _pg_password = os.environ.get("PGPASSWORD", "")
    _pg_database = os.environ.get("PGDATABASE", "collect_ai")
    DB_URL = f"postgresql://{_pg_user}:{_pg_password}@{_pg_host}:{_pg_port}/{_pg_database}"
