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

-- ── AI Reasoning (ai-reasoning-api-upgrade-tasks.md) ────────────────────
-- Grain-nya DEBITUR (cust_id), bukan kontrak — satu debitur bisa punya
-- beberapa kontrak dengan nba_recommendation berbeda-beda; fitur ini
-- merekonsiliasi jadi satu strategi penanganan per debitur (§1 dokumen).
--
-- source_signature = hash(sorted (contract_no, scoring_date) seluruh
-- kontrak AKTIF milik cust_id) — cache basi otomatis begitu skor
-- diperbarui, kontrak baru ditambahkan, atau kontrak ditutup (§4 dokumen).
-- UNIQUE mengikutsertakan prompt_version supaya histori lama tidak pernah
-- ditimpa saat prompt di-iterasi, dan Model Health bisa menghitung rasio
-- OK/FALLBACK/FAILED lintas waktu — karena itu PK-nya SERIAL, bukan cust_id
-- polos.
CREATE TABLE IF NOT EXISTS ai_reasoning_output (
    id                          SERIAL PRIMARY KEY,
    cust_id                     VARCHAR(50) NOT NULL,
    source_signature            VARCHAR(64) NOT NULL,
    prompt_version              VARCHAR(20) NOT NULL,
    -- OK / FALLBACK / FAILED / RUNNING / INSUFFICIENT_DATA — lihat §8.2 dokumen
    status                      VARCHAR(20) NOT NULL,
    -- NO_CBS / TOO_FEW_PAYMENTS / NO_SCORE / TOO_MANY_CONTRACTS / TOO_NEW
    insufficient_reason         VARCHAR(40),
    model_used                  VARCHAR(60),
    generated_at                TIMESTAMPTZ,
    summary                     TEXT,
    customer_treatment_strategy TEXT,
    key_factors                 JSONB,
    -- WA / Deskcoll / Visit / Somasi / Pickup — 5 nilai nyata, lihat
    -- business_rules.py CHANNEL_RANK (satu sumber kebenaran, tidak diketik
    -- ulang di sini sebagai CHECK constraint supaya tidak drift kalau
    -- CHANNEL_RANK berubah).
    primary_nba_action          VARCHAR(20),
    primary_nba_rationale       TEXT,
    nba_agreement               VARCHAR(10),   -- AGREE / DIFFER
    per_contract_focus          JSONB,
    consistency_note            TEXT,
    analyzed_contract_nos       JSONB,
    -- Observabilitas & biaya (§10 dokumen — endpoint ini memicu panggilan
    -- berbayar ke pihak ketiga, wajib bisa dijawab "berapa biayanya").
    latency_ms                  INT,
    prompt_tokens               INT,
    completion_tokens           INT,
    total_tokens                INT,
    error_code                  VARCHAR(60),
    payload_bytes               INT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cust_id, source_signature, prompt_version)
);
CREATE INDEX IF NOT EXISTS idx_ai_reasoning_cust
    ON ai_reasoning_output (cust_id, created_at DESC);
