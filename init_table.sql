-- PGSQL
CREATE TABLE IF NOT EXISTS customer_master (
    cust_id VARCHAR(30) PRIMARY KEY,
    cust_age INT,
    cust_occupation VARCHAR(100),
    cust_income_level VARCHAR(50),
    cust_region VARCHAR(100),
    cust_phone VARCHAR(20),
    cust_segment VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS contract_snapshot (
    contract_no VARCHAR(30) PRIMARY KEY,
    cust_id VARCHAR(30),
        --REFERENCES customer_master(cust_id) ON DELETE CASCADE,
    dpd_current INT CHECK (dpd_current >= 0),
    prnc_ots NUMERIC(15, 2) CHECK (prnc_ots >= 0),
    intr_ots NUMERIC(15, 2) CHECK (intr_ots >= 0),
    cycle VARCHAR(20),
    product_type VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS payment_history (
    payment_id VARCHAR(30) PRIMARY KEY,
    contract_no VARCHAR(30),
        --REFERENCES contract_snapshot(contract_no) ON DELETE CASCADE,
    due_date DATE,
    actual_pay_date DATE,
    payment_amount NUMERIC(15, 2) CHECK (payment_amount >= 0),
    pay_status VARCHAR(20),
    pay_method VARCHAR(50),
    delay_days INTEGER
);

CREATE TABLE IF NOT EXISTS lkp_interaction (
    lkp_id VARCHAR(30) PRIMARY KEY,
    contract_no VARCHAR(30),
        --REFERENCES contract_snapshot(contract_no) ON DELETE CASCADE,
    action_date DATE,
    treatment_type VARCHAR(50),
    result_code VARCHAR(50),
    promise_date DATE,
    collector_id VARCHAR(30),
    interaction_score INTEGER --CHECK (interaction_score > 0 AND interaction_score < 6)
);

CREATE TABLE IF NOT EXISTS collection_analysis (
    contract_no VARCHAR(30) PRIMARY KEY REFERENCES contract_snapshot(contract_no) ON DELETE CASCADE,
    cust_id VARCHAR(30),
        --REFERENCES customer_master(cust_id) ON DELETE CASCADE,
    recovery_score FLOAT CHECK (recovery_score >= 0 AND recovery_score <= 1),
    risk_segment VARCHAR(20),
    nba_recommendation VARCHAR(20),
    priority_level VARCHAR(20),
    confidence_level FLOAT CHECK (confidence_level >= 0 AND confidence_level <= 1),
    scoring_date DATE
);

CREATE TABLE IF NOT EXISTS customer_analysis (
    cust_id VARCHAR(30) PRIMARY KEY REFERENCES customer_master(cust_id) ON DELETE CASCADE,
    active_contract_count INT CHECK (active_contract_count >= 0),
    total_active_ots NUMERIC(15, 2) CHECK (total_active_ots >= 0),
    behavioral_grade CHAR(5), --CHECK (behavioral_grade IN ('A', 'B', 'C', 'D')),
    recovery_effort_level VARCHAR(20),
    ptp_reliability_index FLOAT CHECK (ptp_reliability_index >= 0 AND ptp_reliability_index <= 1),
    collection_sensitivity VARCHAR(50),
    b_list_status CHAR(1) CHECK (b_list_status IN ('Y', 'N')),
    update_timestamp TIMESTAMP
);

-- | Parameter | Nilai Default | Keterangan |
-- |---|---|---|
-- | `PTP_DAYS_WINDOW` | 7 hari | Batas hari setelah PROMISE_DATE untuk dianggap "PTP kept" |
-- | `THRESHOLD_OTS_RENDAH` | 5.000.000 | Batas bawah OTS untuk priority matrix |
-- | `THRESHOLD_OTS_TINGGI` | 20.000.000 | Batas atas OTS untuk priority matrix |
-- | `BROKEN_PTP_BLACLIST` | 5 | Jumlah broken PTP untuk masuk B_LIST |
-- | `HISTORICAL_DEFAULT_BLACKLIST` | 3 | Jumlah kontrak C3+ untuk masuk B_LIST |
-- | `DELAY_TREND_WINDOW` | 6 bulan | Window historis untuk hitung delay_trend |
-- | `REJECTION_THRESHOLD` | 2 | Jumlah penolakan untuk klasifikasi Won't Pay |
-- | `SEGMENT_SHIFT_ALERT` | 15% | Batas perubahan distribusi yang memicu alert |
-- | `RECENCY_WEIGHT_DECAY` | 0.7 | Bobot kontrak lama vs kontrak terbaru |
-- | `INCOME_LOW_PROXY` | 3.000.000 | Proxy pendapatan bulanan untuk INCOME_LEVEL=Low |
-- | `INCOME_MID_PROXY` | 8.000.000 | Proxy pendapatan bulanan untuk INCOME_LEVEL=Mid |
-- | `INCOME_HIGH_PROXY` | 20.000.000 | Proxy pendapatan bulanan untuk INCOME_LEVEL=High |

-- CREATE TABLE IF NOT EXISTS treshold_config (
--     treshold_name VARCHAR(50) PRIMARY KEY,
--     treshold_value BIGINT,
--     description TEXT
-- );

-- INSERT INTO treshold_config (treshold_name, treshold_value, description) VALUES
-- ('PTP_DAYS_WINDOW', 7, 'Days after PROMISE_DATE to consider "PTP kept"'),
-- ('THRESHOLD_OTS_LOW', 5000000, 'Lower threshold of OTS for priority matrix'),
-- ('THRESHOLD_OTS_HIGH', 20000000, 'Upper threshold of OTS for priority matrix'),
-- ('BROKEN_PTP_BLACKLIST', 5, 'Number of broken PTPs to enter B_LIST'),
-- ('HISTORICAL_DEFAULT_BLACKLIST', 3, 'Number of C3+ contracts to enter B_LIST'),
-- ('DELAY_TREND_WINDOW', 6, 'Historical window to calculate delay_trend'),
-- ('REJECTION_THRESHOLD', 2, 'Number of rejections for Won''t Pay classification'),
-- ('SEGMENT_SHIFT_ALERT', 15, 'Threshold for distribution change that triggers alert'),
-- ('RECENCY_WEIGHT_DECAY', 0.7, 'Weight of old contracts vs latest contract'),
-- ('INCOME_LOW_PROXY', 3000000, 'Monthly income proxy for INCOME_LEVEL=Low'),
-- ('INCOME_MID_PROXY', 8000000, 'Monthly income proxy for INCOME_LEVEL=Mid'),
-- ('INCOME_HIGH_PROXY', 20000000, 'Monthly income proxy for INCOME_LEVEL=High');