-- Tabel governance baru yang DIMILIKI app/backend/ (frontend-layout-upgrade-tasks.md
-- TASK-E/TASK-F) — terpisah dari tabel customer_master/dst milik app/machine-learning/
-- (schema_combined.sql) meski tetap satu Postgres yang sama. Idempotent — aman
-- dijalankan berkali-kali.
--
-- Cara pakai:
--   psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f app/backend/db/schema_governance.sql

-- ── TASK-F: Bobot CBS + Model Health (AI Intelligence) ──────────────────
-- Satu baris JSONB per config_key (bukan 1 baris per bobot) supaya PUT
-- weighting-parameters cukup 1 UPDATE atomik untuk seluruh array 4 bobot
-- sekaligus (butuh tervalidasi sum=100% sebagai SATU unit, bukan per-baris).
CREATE TABLE IF NOT EXISTS model_governance_config (
    config_key   VARCHAR(100) PRIMARY KEY,
    config_value JSONB NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_governance_audit_log (
    id           SERIAL PRIMARY KEY,
    action       VARCHAR(50) NOT NULL,      -- e.g. 'WEIGHTING_UPDATE'
    performed_by VARCHAR(150),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    detail       JSONB
);

-- ── TASK-E: Audit approve/reject Restructuring Approval ─────────────────
CREATE TABLE IF NOT EXISTS restructuring_approval_log (
    id                    SERIAL PRIMARY KEY,
    restructure_group_id  VARCHAR(40) NOT NULL,
    action                VARCHAR(20) NOT NULL CHECK (action IN ('APPROVE','REJECT')),
    performed_by          VARCHAR(150),
    performed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_audit_performed_at
    ON model_governance_audit_log (performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_restructuring_approval_group
    ON restructuring_approval_log (restructure_group_id);
