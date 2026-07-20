-- app/machine-learning/config/schema_combined.sql
-- Schema gabungan CollectAI ML (schema.sql v1 + schema_v2.sql upgrade)
-- Ditulis sebagai fresh install — semua kolom upgrade sudah menyatu
-- langsung di CREATE TABLE (bukan ALTER TABLE terpisah).
--
-- Gunakan file ini untuk instalasi baru. schema.sql dan schema_v2.sql
-- tetap dipertahankan sebagai riwayat migrasi bertahap (v1 -> v2).

-- ── INPUT TABLES (read-only sumber data) ──────────────────────────

CREATE TABLE IF NOT EXISTS customer_master (
    cust_id             VARCHAR(30)  PRIMARY KEY,
    cust_age            INT,
    cust_occupation     VARCHAR(100),
    cust_income_level   VARCHAR(50),
    cust_region         VARCHAR(100),
    cust_phone          VARCHAR(20),
    cust_segment        VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS contract_snapshot (
    contract_no                 VARCHAR(30)     PRIMARY KEY,
    cust_id                     VARCHAR(30),
        --REFERENCES customer_master(cust_id) ON DELETE CASCADE,
    dpd_current                 INT             CHECK (dpd_current >= 0),
    prnc_ots                    NUMERIC(15, 2)  CHECK (prnc_ots >= 0),
    intr_ots                    NUMERIC(15, 2)  CHECK (intr_ots >= 0),
    cycle                       VARCHAR(20),
    product_type                VARCHAR(50),
    -- ── kolom upgrade (eks schema_v2) ──
    ambc                        DECIMAL(18, 2),
    prev_cycle                  VARCHAR(10),
    loan_amount                 DECIMAL(18, 2),
    installment_amount          DECIMAL(18, 2),
    maturity_date                DATE,
    overdue_installment_count   INTEGER         DEFAULT 0,
    late_fee_amount              DECIMAL(18, 2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payment_history (
    payment_id          VARCHAR(30)     PRIMARY KEY,
    contract_no         VARCHAR(30),
        --REFERENCES contract_snapshot(contract_no) ON DELETE CASCADE,
    due_date            DATE,
    actual_pay_date     DATE,
    payment_amount      NUMERIC(15, 2)  CHECK (payment_amount >= 0),
    pay_status          VARCHAR(20),
    pay_method          VARCHAR(50),
    delay_days          INTEGER,
    -- ── kolom upgrade (eks schema_v2) ──
    self_cure_flag      BOOLEAN         DEFAULT FALSE,
    recovery_source     VARCHAR(20)     CHECK (recovery_source IS NULL OR
                                                recovery_source IN ('WA', 'SMS', 'Deskcoll', 'Visit', 'Somasi'))
);

CREATE TABLE IF NOT EXISTS lkp_interaction (
    lkp_id                  VARCHAR(30)     PRIMARY KEY,
    contract_no             VARCHAR(30),
        --REFERENCES contract_snapshot(contract_no) ON DELETE CASCADE,
    action_date             DATE,
    treatment_type          VARCHAR(50),
    result_code             VARCHAR(50),
    promise_date            DATE,
    collector_id            VARCHAR(30),
    interaction_score       INTEGER,        --CHECK (interaction_score > 0 AND interaction_score < 6)
    -- ── kolom upgrade (eks schema_v2) ──
    ptp_amount              DECIMAL(18, 2),
    ptp_status              VARCHAR(20)     CHECK (ptp_status IS NULL OR
                                                    ptp_status IN ('OPEN', 'KEPT', 'BROKEN')),
    rpc_flag                BOOLEAN         DEFAULT FALSE,
    contact_success_flag    BOOLEAN         DEFAULT FALSE
);

-- ── OUTPUT TABLE 1: AI Intelligence Output ────────────────────────
CREATE TABLE IF NOT EXISTS ai_intelligence_output (
    contract_no             VARCHAR(50)    PRIMARY KEY,
    cust_id                 VARCHAR(50)    NOT NULL,
    recovery_score          NUMERIC(5,4)   NOT NULL,
    confidence_level        NUMERIC(5,4)   NOT NULL,
    confidence_category     VARCHAR(10)    NOT NULL,
    risk_segment            VARCHAR(20)    NOT NULL,
    nba_recommendation      VARCHAR(20)    NOT NULL,
    priority_level          VARCHAR(10)    NOT NULL,
    scoring_date            DATE           NOT NULL,
    updated_at              TIMESTAMP      DEFAULT NOW(),
    -- ── kolom upgrade (eks schema_v2) — output 3 sub-model baru ──
    self_cure_probability    NUMERIC(5,4),
    roll_forward_risk        NUMERIC(5,4),
    ptp_success_probability  NUMERIC(5,4)
);

-- ── OUTPUT TABLE 2: Customer Behavioral Standing ──────────────────
CREATE TABLE IF NOT EXISTS customer_behavioral_standing (
    cust_id                   VARCHAR(50)    PRIMARY KEY,
    active_contract_count     INT            NOT NULL DEFAULT 0,
    total_active_ots          NUMERIC(18,2)  NOT NULL DEFAULT 0,
    behavioral_grade          CHAR(1)        NOT NULL,
    recovery_effort_level     VARCHAR(10)    NOT NULL,
    ptp_reliability_index     NUMERIC(5,4),
    collection_sensitivity    VARCHAR(20),
    b_list_status             CHAR(1)        NOT NULL DEFAULT 'N',
    update_timestamp          TIMESTAMP      DEFAULT NOW()
);

-- ── MLOPS TABLE: Scoring Labels ───────────────────────────────────
CREATE TABLE IF NOT EXISTS scoring_labels (
    id                    SERIAL         PRIMARY KEY,
    contract_no           VARCHAR(50)    NOT NULL,
    cust_id               VARCHAR(50)    NOT NULL,
    scoring_date          DATE           NOT NULL,
    recovery_score        NUMERIC(5,4),
    risk_segment          VARCHAR(20),
    actual_paid           SMALLINT       NOT NULL,
    labeled_date          DATE           NOT NULL,
    -- ── kolom upgrade (eks schema_v2) — label untuk 3 sub-model ──
    actual_self_cure       SMALLINT,      -- 0/1/NULL
    actual_roll_forward    SMALLINT,      -- 0/1/NULL
    actual_ptp_kept        SMALLINT,      -- 0/1/NULL
    UNIQUE (contract_no, scoring_date)
);

-- ── MLOPS TABLE: Shadow Scores ────────────────────────────────────
CREATE TABLE IF NOT EXISTS shadow_scores (
    id                SERIAL         PRIMARY KEY,
    contract_no       VARCHAR(50)    NOT NULL,
    cust_id           VARCHAR(50)    NOT NULL,
    champion_score    NUMERIC(5,4)   NOT NULL,
    challenger_score  NUMERIC(5,4)   NOT NULL,
    score_delta       NUMERIC(6,4)   NOT NULL,
    snapshot_date     DATE           NOT NULL,
    -- model_type: 'recovery' | 'self_cure' | 'roll_forward' | 'ptp_success'
    -- membedakan shadow run ke-4 model_type supaya tidak tercampur saat
    -- evaluasi champion-vs-challenger per model_type (lihat champion_challenger.py)
    model_type        VARCHAR(20)    NOT NULL DEFAULT 'recovery'
);

-- ── MLOPS TABLE: Model Monitoring Log ────────────────────────────
CREATE TABLE IF NOT EXISTS model_monitoring_log (
    id                      SERIAL      PRIMARY KEY,
    run_date                DATE        NOT NULL,
    auc                     NUMERIC(5,4),
    calibration_gap         NUMERIC(5,4),
    n_samples               INT,
    n_critical_drift        INT         DEFAULT 0,
    n_warning_drift         INT         DEFAULT 0,
    retrain_triggered       BOOLEAN     DEFAULT FALSE,
    champion_version        VARCHAR(20),
    notes                   TEXT,
    created_at              TIMESTAMP   DEFAULT NOW()
);

-- ── INDEXES ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ai_output_cust    ON ai_intelligence_output (cust_id);
CREATE INDEX IF NOT EXISTS idx_ai_output_date    ON ai_intelligence_output (scoring_date);
CREATE INDEX IF NOT EXISTS idx_ai_output_prio    ON ai_intelligence_output (priority_level);
CREATE INDEX IF NOT EXISTS idx_labels_date       ON scoring_labels (scoring_date);
CREATE INDEX IF NOT EXISTS idx_shadow_date       ON shadow_scores (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_shadow_model_type  ON shadow_scores (model_type, snapshot_date);

-- ── INDEXES upgrade (eks schema_v2) ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_lkp_ptp_status
  ON lkp_interaction (contract_no, ptp_status);
CREATE INDEX IF NOT EXISTS idx_payment_self_cure
  ON payment_history (contract_no, self_cure_flag);
CREATE INDEX IF NOT EXISTS idx_payment_recovery_source
  ON payment_history (recovery_source);


-- PGPASSWORD=123123 psql -h localhost -U postgres -d collect_ai -c "
-- TRUNCATE TABLE
--   scoring_feature_snapshot, ai_intelligence_output, customer_behavioral_standing,
--   scoring_labels, shadow_scores, model_monitoring_log,
--   lkp_interaction, payment_history, contract_snapshot, customer_master
-- RESTART IDENTITY;
-- " 2>&1