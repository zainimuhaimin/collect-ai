-- Tabel `users` (login/identity) — dimiliki app/backend/ sendiri, terpisah dari
-- tabel customer_master/dst yang dimiliki app/machine-learning/ (schema_combined.sql),
-- meski tetap satu Postgres yang sama. Idempotent — aman dijalankan berkali-kali.
--
-- Cara pakai:
--   psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f app/backend/db/schema_users.sql

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(200) NOT NULL,
    role          VARCHAR(100) NOT NULL,      -- label tampilan bebas, mis. 'Regional Manager' — bukan enum/RBAC
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
