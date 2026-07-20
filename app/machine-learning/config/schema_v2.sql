-- config/schema_v2.sql
-- Upgrade schema CollectAI dengan data tambahan
-- Jalankan SETELAH schema_v1 (config/schema.sql) sudah ada

-- ── CONTRACT SNAPSHOT: 7 kolom baru ──────────────────────────────
ALTER TABLE contract_snapshot
  ADD COLUMN IF NOT EXISTS ambc                    DECIMAL(18,2),
  ADD COLUMN IF NOT EXISTS prev_cycle              VARCHAR(10),
  ADD COLUMN IF NOT EXISTS loan_amount             DECIMAL(18,2),
  ADD COLUMN IF NOT EXISTS installment_amount      DECIMAL(18,2),
  ADD COLUMN IF NOT EXISTS maturity_date           DATE,
  ADD COLUMN IF NOT EXISTS overdue_installment_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS late_fee_amount         DECIMAL(18,2) DEFAULT 0;

-- ── LKP INTERACTION: 4 kolom baru ────────────────────────────────
ALTER TABLE lkp_interaction
  ADD COLUMN IF NOT EXISTS ptp_amount              DECIMAL(18,2),
  ADD COLUMN IF NOT EXISTS ptp_status              VARCHAR(20),
  ADD COLUMN IF NOT EXISTS rpc_flag                BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS contact_success_flag    BOOLEAN DEFAULT FALSE;

-- CHECK constraint PTP_STATUS
ALTER TABLE lkp_interaction
  ADD CONSTRAINT chk_ptp_status
  CHECK (ptp_status IS NULL OR ptp_status IN ('OPEN', 'KEPT', 'BROKEN'));

-- ── PAYMENT HISTORY: 2 kolom baru ────────────────────────────────
ALTER TABLE payment_history
  ADD COLUMN IF NOT EXISTS self_cure_flag          BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS recovery_source         VARCHAR(20);

-- CHECK constraint RECOVERY_SOURCE
ALTER TABLE payment_history
  ADD CONSTRAINT chk_recovery_source
  CHECK (recovery_source IS NULL OR
         recovery_source IN ('WA', 'SMS', 'Deskcoll', 'Visit', 'Somasi'));

-- ── AI INTELLIGENCE OUTPUT: 3 kolom baru ─────────────────────────
ALTER TABLE ai_intelligence_output
  ADD COLUMN IF NOT EXISTS self_cure_probability   NUMERIC(5,4),
  ADD COLUMN IF NOT EXISTS roll_forward_risk       NUMERIC(5,4),
  ADD COLUMN IF NOT EXISTS ptp_success_probability NUMERIC(5,4);

-- ── SCORING LABELS: tambah kolom untuk sub-model labels ──────────
ALTER TABLE scoring_labels
  ADD COLUMN IF NOT EXISTS actual_self_cure        SMALLINT,  -- 0/1/NULL
  ADD COLUMN IF NOT EXISTS actual_roll_forward     SMALLINT,  -- 0/1/NULL
  ADD COLUMN IF NOT EXISTS actual_ptp_kept         SMALLINT;  -- 0/1/NULL

-- ── SCORING LABELS: tambah kolom untuk sub-model labels ──────────
ALTER TABLE scoring_labels
  ADD COLUMN IF NOT EXISTS model_type              VARCHAR(20) DEFAULT 'recovery';

-- ── NEW INDEXES ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_lkp_ptp_status
  ON lkp_interaction (contract_no, ptp_status);
CREATE INDEX IF NOT EXISTS idx_payment_self_cure
  ON payment_history (contract_no, self_cure_flag);
CREATE INDEX IF NOT EXISTS idx_payment_recovery_source
  ON payment_history (recovery_source);
CREATE INDEX IF NOT EXISTS idx_shadow_model_type
  ON shadow_scores (model_type, snapshot_date);
