-- config/schema_v3.sql
-- Restructuring Recommendation Engine — jalankan SETELAH schema_v2
-- (lihat restructuring-engine-tasks.md TASK-48)

-- ── CONTRACT_SNAPSHOT: raw rate + lineage restrukturisasi ──────────
-- interest_rate: BUKAN fitur model scoring (lihat collect-ai-upgrade.md —
-- ditolak sebagai predictor). Field ini murni untuk kalkulasi amortisasi/
-- haircut di restructuring engine, jangan dimasukkan ke FEATURE_COLS manapun.
ALTER TABLE contract_snapshot
  ADD COLUMN IF NOT EXISTS interest_rate          NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS closed_via_restructure BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS new_contract_no        VARCHAR(30);

-- ── CUSTOMER_BEHAVIORAL_STANDING: input guardrail ───────────────────
ALTER TABLE customer_behavioral_standing
  ADD COLUMN IF NOT EXISTS restructure_count      INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_restructure_date  DATE;

-- ── GROUP MAP: 1 tawaran bisa mencakup 1 atau N kontrak ─────────────
CREATE TABLE IF NOT EXISTS restructuring_group_map (
  restructure_group_id  VARCHAR(40)  NOT NULL,
  contract_no           VARCHAR(30)  NOT NULL,
  cust_id               VARCHAR(30)  NOT NULL,
  inclusion_reason      VARCHAR(50),
  PRIMARY KEY (restructure_group_id, contract_no)
);

-- ── OUTPUT: tawaran yang direkomendasikan ───────────────────────────
-- CATATAN: eligibility_tier/eligibility_reasons/source/requested_by
-- aslinya dispesifikasikan di schema_v4.sql (TASK-59), tapi ditarik maju
-- ke sini karena TASK-52 (restructuring_runner.py) butuh menyimpan
-- eligibility_tier sejak batch run pertama — tanpa kolom ini acceptance
-- criteria TASK-52 tidak terpenuhi.
CREATE TABLE IF NOT EXISTS restructuring_recommendation_output (
  restructure_group_id        VARCHAR(40) PRIMARY KEY,
  cust_id                      VARCHAR(30) NOT NULL,
  offer_type                   VARCHAR(20) NOT NULL,
  contract_count_included      INTEGER NOT NULL,
  total_ots_combined           NUMERIC(18,2),
  recommended_new_tenor        INTEGER,
  recommended_new_rate         NUMERIC(6,4),
  recommended_new_installment  NUMERIC(18,2),
  recovery_from_asset          NUMERIC(18,2) DEFAULT 0,
  npv_baseline                 NUMERIC(18,2),
  npv_restructured             NUMERIC(18,2),
  offer_status                 VARCHAR(20) DEFAULT 'GENERATED',
  generated_date                DATE NOT NULL,
  expiry_date                   DATE,
  eligibility_tier             VARCHAR(20) DEFAULT 'AUTO',
  eligibility_reasons          TEXT,
  source                       VARCHAR(20) DEFAULT 'BATCH',
  requested_by                 VARCHAR(50),
  response_date                 DATE,  -- kapan customer benar-benar merespons (accept/reject)
  CONSTRAINT chk_offer_type   CHECK (offer_type IN ('REFINANCE','CONSOLIDATE','TAKEOVER')),
  CONSTRAINT chk_offer_status CHECK (offer_status IN ('GENERATED','OFFERED','ACCEPTED','REJECTED','EXPIRED')),
  CONSTRAINT chk_eligibility_tier CHECK (eligibility_tier IN ('AUTO','MANUAL_REVIEW','BLOCKED')),
  CONSTRAINT chk_source CHECK (source IN ('BATCH','ON_DEMAND'))
);

-- ── HISTORY: hasil aktual — bahan training model acceptance Fase 2 ──
CREATE TABLE IF NOT EXISTS restructuring_history (
  restructure_group_id      VARCHAR(40) NOT NULL,
  offered_date               DATE NOT NULL,
  customer_response          VARCHAR(20),
  response_date               DATE,
  post_restructure_dpd_30d   INTEGER,
  post_restructure_dpd_90d   INTEGER,
  PRIMARY KEY (restructure_group_id, offered_date)
);

-- ── PRODUCT CONVERSION MAPPING (placeholder — lihat Catatan #2) ─────
CREATE TABLE IF NOT EXISTS product_conversion_mapping (
  source_product_type          VARCHAR(50) NOT NULL,
  allowed_target_product_type  VARCHAR(50) NOT NULL,
  conversion_type               VARCHAR(30),
  requires_appraisal            BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (source_product_type, allowed_target_product_type)
);

-- ── ASSET APPRAISAL (input eksternal — bukan hasil AI) ────────────────
CREATE TABLE IF NOT EXISTS asset_appraisal (
  contract_no       VARCHAR(30) NOT NULL,
  asset_id          VARCHAR(40) NOT NULL,
  appraised_value   NUMERIC(18,2) NOT NULL,
  appraisal_date    DATE NOT NULL,
  condition_grade   VARCHAR(10),
  PRIMARY KEY (contract_no, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_restructure_group_cust    ON restructuring_group_map (cust_id);
CREATE INDEX IF NOT EXISTS idx_restructure_output_status ON restructuring_recommendation_output (offer_status);
