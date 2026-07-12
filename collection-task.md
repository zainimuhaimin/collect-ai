# CollectAI — AI Agent Task List
## Blueprint Implementasi Lengkap dari System Rules + Scoring Engine + MLOps Pipeline

> Dokumen ini adalah daftar task terstruktur yang dapat dikerjakan oleh AI agent
> secara berurutan untuk membangun sistem CollectAI dari nol hingga production-ready.
> Setiap task memiliki input, output, dan kriteria keberhasilan yang eksplisit.
>
> Referensi dokumen:
>   - CollectAI_System_Rules.md      → skema, formula, business rules
>   - CollectAI_Scoring_Engine.md    → RECOVERY_SCORE, CONFIDENCE_LEVEL, kode scoring
>   - CollectAI_MLOps_Pipeline.md    → feedback loop, retraining, champion-challenger
>
> Cara penggunaan:
>   Kerjakan task secara berurutan dalam tiap phase.
>   Task dalam satu phase bisa dikerjakan paralel jika tidak ada dependency eksplisit.
>   Centang [ ] menjadi [x] setelah setiap task selesai dan lolos acceptance criteria.

---

## RINGKASAN PHASE

```
PHASE 1 │ Infrastructure & Config         │ T01–T04  │ Fondasi sistem
PHASE 2 │ Feature Engineering             │ T05–T08  │ Transformasi data mentah
PHASE 3 │ Customer Behavioral Standing    │ T09–T11  │ Profil nasabah lintas kontrak
PHASE 4 │ Model Training & Registry       │ T12–T15  │ Build & simpan model awal
PHASE 5 │ Daily Scoring Pipeline          │ T16–T21  │ Produksi AI output harian
PHASE 6 │ MLOps — Feedback Loop           │ T22–T26  │ Sistem yang belajar sendiri
PHASE 7 │ Integration & End-to-End Test   │ T27–T30  │ Validasi keseluruhan sistem
```

---

## PHASE 1 — Infrastructure & Config

---

### TASK-01: Buat Struktur Folder Project
**Status**: [ ] Pending
**Dependencies**: Tidak ada
**Estimasi**: 5 menit

**Instruksi untuk agent:**
Buat struktur folder berikut dari root directory project:

```
collectai/
├── config/
│   └── settings.py          ← threshold dan konfigurasi global
├── data/
│   ├── raw/                 ← data mentah dari sumber (read-only)
│   └── samples/             ← sample data untuk testing
├── models/
│   ├── archive/             ← model lama yang di-retire (backup rollback)
│   └── registry.json        ← model version registry (dibuat otomatis)
├── src/
│   ├── __init__.py
│   ├── feature_engineering.py
│   ├── cbs_builder.py
│   ├── scoring_engine.py
│   ├── business_rules.py
│   ├── outcome_labeler.py
│   ├── model_monitor.py
│   ├── retrain_strategies.py
│   ├── champion_challenger.py
│   └── model_registry.py
├── pipelines/
│   ├── daily_scoring.py     ← entry point harian
│   └── weekly_mlops.py      ← entry point mingguan
├── tests/
│   ├── test_features.py
│   ├── test_rules.py
│   ├── test_scoring.py
│   └── test_mlops.py
├── logs/
│   └── .gitkeep
├── requirements.txt
└── README.md
```

**Acceptance Criteria:**
- [ ] Semua folder dan file placeholder terbuat
- [ ] `__init__.py` ada di folder `src/`
- [ ] `logs/` dan `models/archive/` tersedia

---

### TASK-02: Buat File Konfigurasi Global
**Status**: [ ] Pending
**Dependencies**: TASK-01
**Output file**: `config/settings.py`

**Instruksi untuk agent:**
Buat file `config/settings.py` berisi semua konstanta yang dapat dikonfigurasi
tanpa mengubah kode bisnis. Isi file:

```python
# config/settings.py
# Semua threshold dan konfigurasi CollectAI
# Ubah nilai di sini tanpa perlu menyentuh kode bisnis

# ── DATABASE ──────────────────────────────────────────────────────
DB_URL = "postgresql://user:password@localhost:5432/collectai"

# ── PATH ──────────────────────────────────────────────────────────
CHAMPION_MODEL_PATH    = "models/recovery_model_champion.pkl"
CHALLENGER_MODEL_PATH  = "models/recovery_model_challenger.pkl"
REGISTRY_PATH          = "models/registry.json"
ARCHIVE_DIR            = "models/archive"
LOG_PATH               = "logs/scoring_log.csv"

# ── FEATURE ENGINEERING ───────────────────────────────────────────
PTP_DAYS_WINDOW          = 7     # hari setelah PROMISE_DATE untuk hitung PTP kept
DELAY_TREND_WINDOW_MONTHS = 6    # window bulan untuk hitung delay_trend
LABEL_WINDOW_DAYS        = 30    # hari setelah scoring untuk cek actual payment

# INCOME PROXY (Rp per bulan)
INCOME_PROXY = {
    "Low"  : 3_000_000,
    "Mid"  : 8_000_000,
    "High" : 20_000_000,
}

# ── OTS THRESHOLD (untuk NBA & Priority matrix) ───────────────────
OTS_TIER_RENDAH  = 5_000_000
OTS_TIER_TINGGI  = 20_000_000

# ── RISK SEGMENT THRESHOLDS ───────────────────────────────────────
SCORE_THRESHOLD_WONT_PAY    = 0.30
SCORE_THRESHOLD_CANNOT_PAY  = 0.50
SCORE_THRESHOLD_SELF_CURE   = 0.70
REJECTION_COUNT_THRESHOLD   = 2
MAX_DPD_FOR_SELFCURE        = 7
MIN_PAYMENT_RATE_SELFCURE   = 0.80
MAX_INCOME_DEBT_RATIO       = 2.0

# ── CBS / BEHAVIORAL GRADE ────────────────────────────────────────
GRADE_A_THRESHOLD = 0.80
GRADE_B_THRESHOLD = 0.60
GRADE_C_THRESHOLD = 0.40

# Bobot komponen composite_behavioral_score
WEIGHT_PAYMENT_RATE     = 0.30
WEIGHT_PTP_RELIABILITY  = 0.25
WEIGHT_INTERACTION      = 0.20
WEIGHT_DELAY_SCORE      = 0.25
RECENCY_WEIGHT_DECAY    = 0.70   # per bulan ke belakang

# Threshold B_LIST
BROKEN_PTP_BLACKLIST         = 5
HISTORICAL_DEFAULT_BLACKLIST = 3
PTP_RELIABILITY_BLACKLIST    = 0.10
MIN_PTP_MADE_FOR_BLACKLIST   = 3

# ── MLOPS & MONITORING ────────────────────────────────────────────
AUC_FLOOR               = 0.68    # retrain jika AUC turun di bawah ini
N_CRITICAL_DRIFT_TRIGGER = 2      # retrain jika fitur ini yg PSI > 0.25
N_WARNING_DRIFT_TRIGGER  = 5      # retrain jika fitur ini yg PSI > 0.10
SHADOW_DAYS_MIN          = 7      # minimal shadow sebelum evaluasi
MIN_AUC_IMPROVEMENT      = 0.02   # challenger harus unggul minimal ini
RETRAIN_DECAY_RATE       = 0.70   # recency-weighted decay rate
MIN_SAMPLES_FOR_EVAL     = 200    # minimal records untuk evaluasi model

# ── MODEL TRAINING ────────────────────────────────────────────────
XGB_N_ESTIMATORS     = 500
XGB_MAX_DEPTH        = 6
XGB_LEARNING_RATE    = 0.05
XGB_SUBSAMPLE        = 0.80
XGB_COLSAMPLE        = 0.80
XGB_MIN_CHILD_WEIGHT = 10
XGB_GAMMA            = 1.0
XGB_REG_ALPHA        = 0.1
XGB_REG_LAMBDA       = 1.0
CV_N_SPLITS          = 5
MIN_CV_AUC_TO_DEPLOY = 0.70

# Kolom fitur model — JANGAN ubah tanpa retrain model
FEATURE_COLS = [
    "DPD_CURRENT", "cycle_encoded", "total_ots",
    "payment_rate", "partial_rate", "avg_delay_days",
    "days_since_last_pay", "ptp_fulfillment_rate",
    "avg_interaction_score", "last_result_code_encoded",
    "treatment_count", "rejection_count", "payment_count",
    "ptp_reliability_index", "delay_trend",
    "historical_default_count", "income_debt_ratio",
    "active_contract_count", "total_active_ots",
    "behavioral_grade_encoded", "b_list_flag",
]
TARGET_COL = "actual_paid"
```

**Acceptance Criteria:**
- [ ] File `config/settings.py` terbuat dan bisa di-import tanpa error
- [ ] `from config.settings import FEATURE_COLS` berhasil
- [ ] Semua nilai memiliki komentar penjelasan

---

### TASK-03: Buat Database Schema (DDL)
**Status**: [ ] Pending
**Dependencies**: TASK-01
**Output file**: `config/schema.sql`

**Instruksi untuk agent:**
Buat file SQL DDL untuk semua tabel yang dibutuhkan sistem.

```sql
-- config/schema.sql

-- ── INPUT TABLES (sudah ada di sumber, READ-ONLY) ─────────────────
-- customer_master, contract_snapshot, payment_history, lkp_interaction

-- ── OUTPUT TABLE 1: AI Intelligence Output ────────────────────────
CREATE TABLE IF NOT EXISTS ai_intelligence_output (
    contract_no           VARCHAR(50)    PRIMARY KEY,
    cust_id               VARCHAR(50)    NOT NULL,
    recovery_score        NUMERIC(5,4)   NOT NULL,
    confidence_level      NUMERIC(5,4)   NOT NULL,
    confidence_category   VARCHAR(10)    NOT NULL,  -- HIGH/MEDIUM/LOW
    risk_segment          VARCHAR(20)    NOT NULL,  -- Self-cure/Can Pay/Cannot Pay/Won't Pay
    nba_recommendation    VARCHAR(20)    NOT NULL,  -- WA/Deskcoll/Visit/Somasi/Pickup
    priority_level        VARCHAR(10)    NOT NULL,  -- Critical/High/Medium/Low
    scoring_date          DATE           NOT NULL,
    updated_at            TIMESTAMP      DEFAULT NOW()
);

-- ── OUTPUT TABLE 2: Customer Behavioral Standing ──────────────────
CREATE TABLE IF NOT EXISTS customer_behavioral_standing (
    cust_id                   VARCHAR(50)    PRIMARY KEY,
    active_contract_count     INT            NOT NULL DEFAULT 0,
    total_active_ots          NUMERIC(18,2)  NOT NULL DEFAULT 0,
    behavioral_grade          CHAR(1)        NOT NULL,    -- A/B/C/D
    recovery_effort_level     VARCHAR(10)    NOT NULL,    -- Low/Mid/High
    ptp_reliability_index     NUMERIC(5,4),              -- NULL = belum ada PTP
    collection_sensitivity    VARCHAR(20),               -- channel paling efektif
    b_list_status             CHAR(1)        NOT NULL DEFAULT 'N',
    update_timestamp          TIMESTAMP      DEFAULT NOW()
);

-- ── MLOPS TABLE: Scoring Labels ───────────────────────────────────
CREATE TABLE IF NOT EXISTS scoring_labels (
    id                SERIAL         PRIMARY KEY,
    contract_no       VARCHAR(50)    NOT NULL,
    cust_id           VARCHAR(50)    NOT NULL,
    scoring_date      DATE           NOT NULL,
    recovery_score    NUMERIC(5,4),
    risk_segment      VARCHAR(20),
    actual_paid       SMALLINT       NOT NULL,  -- 0 atau 1
    labeled_date      DATE           NOT NULL,
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
    snapshot_date     DATE           NOT NULL
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
```

**Acceptance Criteria:**
- [ ] File `config/schema.sql` terbuat
- [ ] Semua tabel output terdefinisi dengan tipe data yang tepat
- [ ] Constraint UNIQUE pada `scoring_labels` untuk mencegah duplikat label
- [ ] Index pada kolom yang sering di-query

---

### TASK-04: Buat `requirements.txt`
**Status**: [ ] Pending
**Dependencies**: TASK-01
**Output file**: `requirements.txt`

**Instruksi untuk agent:**
Buat file requirements.txt dengan versi minimum yang diperlukan:

```
xgboost>=1.7.0
scikit-learn>=1.2.0
pandas>=1.5.0
numpy>=1.23.0
joblib>=1.2.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
```

**Acceptance Criteria:**
- [ ] `pip install -r requirements.txt` berhasil tanpa error
- [ ] `import xgboost, sklearn, pandas, numpy, joblib, sqlalchemy` semua berhasil

---

## PHASE 2 — Feature Engineering

---

### TASK-05: Implementasi Contract-Level Feature Engineering
**Status**: [ ] Pending
**Dependencies**: TASK-02, TASK-04
**Output file**: `src/feature_engineering.py` (fungsi pertama)

**Instruksi untuk agent:**
Implementasikan fungsi `compute_contract_features()` di `src/feature_engineering.py`.
Fungsi ini menghasilkan 13 fitur sesuai System Rules Bagian 2.1.

Fungsi harus:
1. Menerima `df_contract`, `df_payment`, `df_lkp`, `reference_date` sebagai input
2. Melakukan LEFT JOIN payment history ke contract snapshot ON CONTRACT_NO
3. Melakukan LEFT JOIN LKP history ke contract snapshot ON CONTRACT_NO
4. Menghitung semua 13 fitur dari System Rules Bagian 2.1:
   - `dpd_current`, `cycle_encoded`, `total_ots`
   - `payment_rate`, `partial_rate`, `avg_delay_days`
   - `days_since_last_pay`, `payment_count`
   - `total_ptp_made`, `total_ptp_kept`, `ptp_fulfillment_rate`
   - `avg_interaction_score`, `treatment_count`, `rejection_count`
   - `last_result_code_encoded` (map: Bayar=4, PTP=3, Rumah Kosong=2, Tidak Bisa=1, Menolak=0)
5. Menggunakan `PTP_DAYS_WINDOW` dari `config/settings.py`
6. Return DataFrame dengan 1 baris per CONTRACT_NO

**Acceptance Criteria:**
- [ ] Fungsi berjalan tanpa error pada sample data
- [ ] Semua 13 fitur hadir di output DataFrame
- [ ] `payment_rate` dalam range [0.0, 1.0]
- [ ] `ptp_fulfillment_rate` NULL jika `total_ptp_made = 0` (bukan 0)
- [ ] `cycle_encoded` hanya berisi nilai 0, 1, 2, atau 3
- [ ] `last_result_code_encoded` hanya berisi 0–4

---

### TASK-06: Implementasi Customer-Level Feature Engineering
**Status**: [ ] Pending
**Dependencies**: TASK-05
**Output file**: `src/feature_engineering.py` (fungsi kedua)

**Instruksi untuk agent:**
Tambahkan fungsi `compute_customer_features()` ke `src/feature_engineering.py`.
Fungsi ini mengagregasi data lintas semua kontrak per CUST_ID.

Fungsi harus menghasilkan 8 fitur sesuai System Rules Bagian 2.2:
- `active_contract_count`: COUNT(kontrak aktif) per CUST_ID
- `total_active_ots`: SUM(PRNC_OTS + INTR_OTS) kontrak aktif per CUST_ID
- `ptp_reliability_index`: SUM(ptp_kept) / SUM(ptp_made) LINTAS SEMUA kontrak
- `broken_ptp_count`: SUM(ptp_made - ptp_kept) lintas semua kontrak
- `delay_trend`: slope linear dari AVG(DELAY_DAYS) per bulan dalam 6 bulan terakhir
  (positif = memburuk, negatif = membaik, 0 = datar)
- `channel_effectiveness`: MODE(TREATMENT_TYPE) WHERE RESULT_CODE='Bayar'
- `historical_default_count`: COUNT(kontrak yang pernah cycle C3+) per CUST_ID
- `income_debt_ratio`: total_active_ots / income_proxy dari INCOME_PROXY config
- `composite_behavioral_score`: weighted average sesuai rumus System Rules Bagian 2.2

Formula `composite_behavioral_score`:
```python
payment_rate_weighted  = avg(payment_rate per kontrak, recency-weighted)
ptp_reliability_index  = sudah dihitung
interaction_score_norm = (avg_interaction_score - 1) / 4   # normalize 1-5 ke 0-1
delay_score            = max(0, 1 - (avg_delay_days / 90)) # 0 hari=1.0, 90hari=0.0

composite = (payment_rate_weighted * 0.30
           + ptp_reliability_index  * 0.25
           + interaction_score_norm * 0.20
           + delay_score            * 0.25)
```

**Acceptance Criteria:**
- [ ] Fungsi menghasilkan 1 baris per CUST_ID (bukan per CONTRACT)
- [ ] `composite_behavioral_score` dalam range [0.0, 1.0]
- [ ] `delay_trend` bisa negatif (perbaikan) atau positif (memburuk)
- [ ] `ptp_reliability_index` NULL jika tidak pernah ada PTP (bukan 0.0)
- [ ] `channel_effectiveness` NULL jika belum pernah ada pembayaran setelah interaksi
- [ ] Test: nasabah dengan 3 kontrak aktif → `active_contract_count = 3`

---

### TASK-07: Implementasi `enrich_with_cbs()`
**Status**: [ ] Pending
**Dependencies**: TASK-06
**Output file**: `src/feature_engineering.py` (fungsi ketiga)

**Instruksi untuk agent:**
Tambahkan fungsi `enrich_with_cbs(df_contract_features, df_cbs)` yang:
1. Mengambil kolom relevan dari CBS: `CUST_ID`, `ptp_reliability_index`,
   `delay_trend`, `historical_default_count`, `income_debt_ratio`,
   `active_contract_count`, `total_active_ots`, `BEHAVIORAL_GRADE`, `B_LIST_STATUS`
2. Encode `BEHAVIORAL_GRADE` → `behavioral_grade_encoded` (A=3, B=2, C=1, D=0)
3. Encode `B_LIST_STATUS` → `b_list_flag` (Y=1, N=0)
4. LEFT JOIN ke contract features pada CUST_ID
5. Return enriched DataFrame

**Acceptance Criteria:**
- [ ] Output memiliki semua kolom dari `FEATURE_COLS` di settings.py
- [ ] Tidak ada duplikat CONTRACT_NO di output
- [ ] Kontrak dari nasabah yang belum ada di CBS → nilai CBS = NULL (bukan error)
- [ ] `behavioral_grade_encoded` hanya berisi 0, 1, 2, 3, atau NULL

---

### TASK-08: Unit Test Feature Engineering
**Status**: [ ] Pending
**Dependencies**: TASK-05, TASK-06, TASK-07
**Output file**: `tests/test_features.py`

**Instruksi untuk agent:**
Buat file test menggunakan `pytest` dengan minimal 8 test case:

```python
# Test cases yang harus ada:
1. test_payment_rate_full()          # nasabah 3x Full → rate = 1.0
2. test_payment_rate_mixed()         # 1 Full, 1 Partial, 1 None → rate = 0.33
3. test_ptp_fulfillment_no_ptp()     # tidak ada PTP → ptp_fulfillment_rate = NULL
4. test_ptp_fulfillment_kept()       # PTP dibuat, bayar 5 hari kemudian → kept = 1
5. test_ptp_fulfillment_broken()     # PTP dibuat, tidak bayar → kept = 0
6. test_cycle_encoding()             # C0→0, C1→1, C2→2, C3→3
7. test_customer_multi_contract()    # 1 nasabah, 3 kontrak → count=3, OTS=sum
8. test_delay_trend_worsening()      # delay naik setiap bulan → trend > 0
9. test_enrichment_no_cbs()         # kontrak baru tanpa CBS → tidak error, CBS=NULL
10. test_enrichment_all_features()   # semua kolom FEATURE_COLS hadir di output
```

Gunakan `pd.DataFrame` kecil sebagai mock data — tidak perlu koneksi database.

**Acceptance Criteria:**
- [ ] `pytest tests/test_features.py` → semua test PASS
- [ ] Coverage minimal 80% untuk `src/feature_engineering.py`

---

## PHASE 3 — Customer Behavioral Standing (CBS)

---

### TASK-09: Implementasi Business Rules CBS
**Status**: [ ] Pending
**Dependencies**: TASK-06
**Output file**: `src/cbs_builder.py`

**Instruksi untuk agent:**
Buat `src/cbs_builder.py` dengan fungsi `build_cbs(df_customer_features)`.
Fungsi ini menerapkan semua business rules dari System Rules Bagian 4.

Rules yang harus diimplementasikan (dalam urutan ini):

**BEHAVIORAL_GRADE** (dari `composite_behavioral_score`):
```python
A jika score >= 0.80
B jika score >= 0.60
C jika score >= 0.40
D jika score < 0.40

Override paksa ke D jika:
  broken_ptp_count >= 5  ATAU
  historical_default_count >= 3  ATAU
  ptp_reliability_index < 0.10 DAN total_ptp_made >= 3
```

**RECOVERY_EFFORT_LEVEL**:
```python
Low  → Grade A
Mid  → Grade B atau C
High → Grade D, atau B_LIST_STATUS='Y', atau active_contract_count >= 3
```

**PTP_RELIABILITY_INDEX**: langsung dari customer features
(NULL jika total_ptp_made = 0)

**COLLECTION_SENSITIVITY**: langsung dari channel_effectiveness
(dengan fallback ke default per CUST_SEGMENT jika NULL)

**B_LIST_STATUS** (Y jika salah satu):
```python
- BEHAVIORAL_GRADE = 'D'
- broken_ptp_count >= 5
- Pernah ada TREATMENT_TYPE = 'Somasi Hukum' atau 'Pickup'
- historical_default_count >= 3
- ptp_reliability_index < 0.10 DAN total_ptp_made >= 3
```

Catatan: `B_LIST_STATUS = 'Y'` TIDAK otomatis kembali ke 'N'.
Jika baris sudah ada di database dengan B_LIST = 'Y', jangan di-override ke 'N'
kecuali ada flag `force_reset=True`.

**Acceptance Criteria:**
- [ ] Fungsi menghasilkan DataFrame dengan semua kolom CBS (lihat schema TASK-03)
- [ ] `BEHAVIORAL_GRADE` selalu A, B, C, atau D — tidak pernah NULL
- [ ] `B_LIST_STATUS` selalu 'Y' atau 'N' — tidak pernah NULL
- [ ] Override Grade D bekerja: nasabah dengan broken_ptp=6 → Grade D meski score=0.75
- [ ] B_LIST tidak di-reset: nasabah yang sudah Y tetap Y setelah update

---

### TASK-10: Implementasi CBS Update Pipeline
**Status**: [ ] Pending
**Dependencies**: TASK-09
**Output file**: `src/cbs_builder.py` (fungsi kedua)

**Instruksi untuk agent:**
Tambahkan fungsi `update_cbs(engine, reference_date)` yang:

1. Load data dari database (contract_snapshot, payment_history, lkp_interaction, customer_master)
2. Hitung customer features menggunakan `compute_customer_features()` (TASK-06)
3. Hitung CBS rules menggunakan `build_cbs()` (TASK-09)
4. Load CBS yang sudah ada dari database
5. **PENTING — Preserve B_LIST_STATUS**: Jika nasabah sudah B_LIST='Y' di database, jangan di-reset ke 'N' dari perhitungan baru
6. UPSERT ke tabel `customer_behavioral_standing` (insert baru, update jika sudah ada)
7. Set `update_timestamp = NOW()`
8. Log jumlah records: inserted, updated, B_LIST preserved

Tambahkan juga fungsi triggered: `update_cbs_for_customer(cust_id, engine)` untuk
update satu nasabah saja (dipakai saat kontrak closed).

**Acceptance Criteria:**
- [ ] Fungsi berjalan tanpa error
- [ ] B_LIST_STATUS yang sudah 'Y' tidak berubah menjadi 'N' setelah update
- [ ] `update_timestamp` diperbarui setiap kali ada perubahan
- [ ] Tidak ada duplikat CUST_ID di tabel output
- [ ] Nasabah yang tidak ada perubahannya di-skip (tidak di-update timestamp-nya)

---

### TASK-11: Unit Test CBS
**Status**: [ ] Pending
**Dependencies**: TASK-09, TASK-10
**Output file**: `tests/test_cbs.py`

**Instruksi untuk agent:**
Buat test cases:

```python
1. test_grade_a()               # score=0.85 → Grade A
2. test_grade_d_override()      # score=0.75 tapi broken_ptp=6 → Grade D (override)
3. test_blist_stays_y()         # B_LIST sudah Y di DB → tetap Y setelah update
4. test_blist_from_somasi()     # pernah ada TREATMENT='Somasi Hukum' → B_LIST=Y
5. test_effort_level_high()     # Grade D → High effort
6. test_effort_level_high_multicontract()  # Grade B + 3 kontrak aktif → High effort
7. test_ptp_index_null()        # belum pernah PTP → index=NULL bukan 0
8. test_recovery_effort_mid()   # Grade B → Mid effort
```

**Acceptance Criteria:**
- [ ] Semua test PASS
- [ ] `pytest tests/test_cbs.py -v` menampilkan nama test dan status

---

## PHASE 4 — Model Training & Registry

---

### TASK-12: Implementasi Outcome Labeler (Training Target)
**Status**: [ ] Pending
**Dependencies**: TASK-04
**Output file**: `src/outcome_labeler.py`

**Instruksi untuk agent:**
Implementasikan dua fungsi:

**Fungsi 1**: `build_target_variable(df_features, df_payment, scoring_date, n_days=30)`
Digunakan saat training awal — membuat label untuk dataset historis.
Return: df_features dengan kolom tambahan `actual_paid` (0 atau 1).

**Fungsi 2**: `label_historical_scores(df_ai_output, df_payment, engine=None, label_window=30)`
Digunakan oleh MLOps weekly — melabeli scoring records yang sudah cukup tua.
Return: DataFrame labeled records baru (yang belum ada di scoring_labels).
Jika `engine` tidak None, append ke tabel `scoring_labels`.

Kedua fungsi menggunakan logika yang sama:
- Payment FULL atau PARTIAL dalam window → `actual_paid = 1`
- Tidak ada payment dalam window → `actual_paid = 0`

**Acceptance Criteria:**
- [ ] `actual_paid` selalu 0 atau 1, tidak pernah NULL
- [ ] Tidak ada double-labeling: kontrak yang sudah ada di `scoring_labels` tidak di-append ulang
- [ ] Print summary: total labeled, n_paid, n_unpaid, paid rate

---

### TASK-13: Implementasi Training Pipeline
**Status**: [ ] Pending
**Dependencies**: TASK-02, TASK-12
**Output file**: `src/retrain_strategies.py`

**Instruksi untuk agent:**
Implementasikan tiga strategi training dari MLOps Pipeline Bagian 6:

**`strategy_full_retrain(df_labeled, feature_cols, target_col)`**
Train dengan semua data. Gunakan parameter XGB dari settings.py.
Jalankan 5-fold cross-validation. Return (model, metadata_dict).

**`strategy_rolling_window(df_labeled, feature_cols, target_col, months=6)`**
Filter hanya data N bulan terakhir. Raise error jika < 500 records.
Return (model, metadata_dict).

**`strategy_recency_weighted(df_labeled, feature_cols, target_col, decay_rate=0.70)`**
Hitung `sample_weight = decay_rate ** months_ago`.
Train dengan `model.fit(X, y, sample_weight=w)`.
Evaluasi AUC pada data 1 bulan terakhir saja.
Return (model, metadata_dict).

Setiap fungsi harus:
- Menggunakan konfigurasi XGB dari settings.py
- Return model dan dict metadata (strategy, n_samples, auc, trained_at)
- Raise `ValueError` jika CV AUC < `MIN_CV_AUC_TO_DEPLOY`

**Acceptance Criteria:**
- [ ] Semua 3 fungsi bisa dipanggil dengan sample DataFrame
- [ ] Return tuple (model, dict) dengan format konsisten
- [ ] Raise ValueError jika AUC di bawah threshold
- [ ] `strategy_recency_weighted` dengan decay=0.7 → data bulan lalu bobotnya 0.7×

---

### TASK-14: Implementasi Model Registry
**Status**: [ ] Pending
**Dependencies**: TASK-13
**Output file**: `src/model_registry.py`

**Instruksi untuk agent:**
Implementasikan model registry berbasis JSON file (path dari settings.py).

Fungsi yang harus ada:
- `register_model(model_path, metadata, role='challenger')` → return version string
- `get_champion_path()` → return path model champion aktif
- `get_challenger_path()` → return path challenger, None jika tidak ada
- `get_performance_history(last_n=10)` → print tabel history dan return list
- `rollback_to_previous()` → ganti champion ke versi sebelumnya
- `_load_registry()` / `_save_registry()` → helper private

Format registry.json:
```json
{
  "current_champion": {"version": "v1", "path": "...", "cv_auc": 0.73, ...},
  "current_challenger": null,
  "history": [...]
}
```

**Acceptance Criteria:**
- [ ] `register_model()` menambah entry ke history dan update current role
- [ ] `rollback_to_previous()` berhasil jika ada minimal 2 champion di history
- [ ] `rollback_to_previous()` raise error jika tidak ada previous champion
- [ ] registry.json terbuat otomatis jika belum ada

---

### TASK-15: Training Model Awal
**Status**: [ ] Pending
**Dependencies**: TASK-13, TASK-14
**Output file**: `models/recovery_model_champion.pkl`

**Instruksi untuk agent:**
Buat script `pipelines/train_initial_model.py` yang:

1. Load data historis dari database (minimal 6 bulan ke belakang)
2. Hitung contract features (TASK-05)
3. Hitung dan update CBS (TASK-10)
4. Enrich dengan CBS (TASK-07)
5. Build target variable dengan `build_target_variable()` (TASK-12)
6. Cek distribusi label (print paid rate — idealnya 30–70%)
7. Train dengan `strategy_recency_weighted()` (TASK-13)
8. Simpan model artifact ke `CHAMPION_MODEL_PATH`, termasuk:
   ```python
   {
     'model': trained_model,
     'feature_cols': FEATURE_COLS,
     'trained_at': timestamp,
     'metadata': metadata_dict,
     'training_features_sample': X.sample(min(1000, len(X)))  # untuk drift detection
   }
   ```
9. Register ke model registry sebagai 'champion'
10. Print: CV AUC, feature importance top 10

**Acceptance Criteria:**
- [ ] File `models/recovery_model_champion.pkl` terbuat
- [ ] CV AUC minimal 0.70 (threshold dari settings.py)
- [ ] Model artifact menyimpan `training_features_sample` untuk future drift detection
- [ ] `models/registry.json` terbuat dengan entry champion v1
- [ ] Feature importance dicetak ke console

---

## PHASE 5 — Daily Scoring Pipeline

---

### TASK-16: Implementasi Scoring Engine
**Status**: [ ] Pending
**Dependencies**: TASK-14, TASK-15
**Output file**: `src/scoring_engine.py`

**Instruksi untuk agent:**
Implementasikan fungsi `score_contracts(df_features_enriched, model_path)`:
1. Load model artifact dari model_path
2. Extract model dan feature_cols dari artifact
3. `RECOVERY_SCORE = model.predict_proba(X)[:, 1].round(4)`
4. Return DataFrame dengan kolom `RECOVERY_SCORE` ditambahkan

**Acceptance Criteria:**
- [ ] `RECOVERY_SCORE` dalam range [0.0000, 1.0000]
- [ ] Tidak ada NULL di `RECOVERY_SCORE`
- [ ] Fungsi menggunakan `feature_cols` dari artifact model (bukan hardcode)

---

### TASK-17: Implementasi Confidence Level
**Status**: [ ] Pending
**Dependencies**: TASK-16
**Output file**: `src/scoring_engine.py` (tambahkan fungsi)

**Instruksi untuk agent:**
Tambahkan fungsi `compute_confidence_level(df)` sesuai Scoring Engine Bagian 5.

Tiga komponen (formula dari dokumen):
- **A — Data Completeness (bobot 0.40)**: % dari 5 fitur kunci yang tidak NULL
  `['avg_delay_days', 'payment_rate', 'ptp_fulfillment_rate', 'avg_interaction_score', 'ptp_reliability_index']`
- **B — History Depth (bobot 0.35)**: normalized payment_count (cap 10) × 0.6 + treatment_count (cap 5) × 0.4
- **C — Model Certainty (bobot 0.25)**: `2 × |RECOVERY_SCORE − 0.5|`

`CONFIDENCE_LEVEL = A×0.40 + B×0.35 + C×0.25`
`CONFIDENCE_CATEGORY`: HIGH (≥0.75), MEDIUM (≥0.50), LOW (<0.50)

**Acceptance Criteria:**
- [ ] `CONFIDENCE_LEVEL` dalam range [0.0, 1.0]
- [ ] Kontrak tanpa payment history → completeness rendah → confidence LOW
- [ ] `RECOVERY_SCORE = 0.5` → certainty = 0 → confidence lebih rendah
- [ ] Semua 3 sub-komponen tersimpan sebagai kolom terpisah (untuk debugging)

---

### TASK-18: Implementasi Business Rules
**Status**: [ ] Pending
**Dependencies**: TASK-17
**Output file**: `src/business_rules.py`

**Instruksi untuk agent:**
Implementasikan semua business rules dari System Rules Bagian 3.

**`apply_risk_segment(df)`**:
Evaluasi top-down, first-match:
1. Won't Pay: `score < 0.30 AND (rejection >= 2 OR last_result <= 1)`
2. Cannot Pay: `0.30 ≤ score < 0.50 AND (broken_ptp > 0 OR income_debt_ratio > 2.0)`
3. Self-cure: `score ≥ 0.70 AND dpd ≤ 7 AND payment_rate ≥ 0.80`
4. Can Pay: semua lainnya

**`apply_nba(df, df_cbs)`**:
Sesuai decision table System Rules Bagian 3.4.
Override dengan `COLLECTION_SENSITIVITY` dari CBS jika channel lebih tinggi ranknya.
Channel rank: WA=1, Deskcoll=2, Visit=3, Somasi=4, Pickup=5.

**`apply_priority(df)`**:
Matrix 4×3 (RISK_SEGMENT × OTS tier) sesuai System Rules Bagian 3.5.
Gunakan `OTS_TIER_RENDAH` dan `OTS_TIER_TINGGI` dari settings.py.

**Acceptance Criteria:**
- [ ] `RISK_SEGMENT` selalu salah satu dari: Self-cure, Can Pay, Cannot Pay, Won't Pay
- [ ] `NBA_RECOMMENDATION` selalu salah satu dari: WA, Deskcoll, Visit, Somasi, Pickup
- [ ] `PRIORITY_LEVEL` selalu: Critical, High, Medium, atau Low
- [ ] Override NBA bekerja: nasabah dengan COLLECTION_SENSITIVITY=Visit dan NBA default=WA → output NBA=Visit
- [ ] Override tidak downgrade: nasabah NBA=Somasi tidak di-override ke WA meski sensitivity=WA

---

### TASK-19: Implementasi Quality Check
**Status**: [ ] Pending
**Dependencies**: TASK-18
**Output file**: `src/scoring_engine.py` (tambahkan fungsi)

**Instruksi untuk agent:**
Implementasikan `run_quality_check(df_output)` sesuai System Rules Bagian 6.

Cek yang harus ada (dari Bagian 6.1, 6.2, 6.3):
- Range check: RECOVERY_SCORE, CONFIDENCE_LEVEL dalam [0,1]
- Null check: kolom wajib tidak boleh NULL
- Duplikat: tidak ada CONTRACT_NO duplikat
- Distribusi: Won't Pay tidak > 30%, Self-cure tidak < 5%
- Distribusi: Critical tidak > 20%
- Konsistensi: setiap CONTRACT_NO harus punya CUST_ID yang ada di CBS

Jika ada cek yang gagal:
- Print warning dengan detail yang gagal
- Raise `ValueError` untuk cek hard (distribusi dan null)
- Hanya warning untuk cek soft (konsistensi)

**Acceptance Criteria:**
- [ ] Raise `ValueError` jika Won't Pay > 30%
- [ ] Raise `ValueError` jika ada NULL di RISK_SEGMENT atau NBA_RECOMMENDATION
- [ ] Print ringkasan semua cek (PASS/FAIL) ke console

---

### TASK-20: Implementasi Daily Scoring Runner
**Status**: [ ] Pending
**Dependencies**: TASK-16, TASK-17, TASK-18, TASK-19
**Output file**: `pipelines/daily_scoring.py`

**Instruksi untuk agent:**
Buat entry point harian `run_daily_scoring(reference_date=None)` yang memanggil
semua fungsi dalam urutan benar (sesuai Daily Batch Flow System Rules Bagian 5):

```
Step 1: Load data dari database
Step 2: Compute contract-level features
Step 3: Load CBS dari database → enrich features
Step 4: Score dengan champion model
Step 5: Compute confidence level
Step 6: Apply business rules (segment, NBA, priority)
Step 7: Quality check
Step 8: UPSERT ke ai_intelligence_output
Step 9: Log run ke scoring_log.csv
Step 10: Print summary
```

Jika step 7 gagal → stop, tidak publish, kirim error log.
Jika sukses → print breakdown per RISK_SEGMENT dan PRIORITY_LEVEL.

**Acceptance Criteria:**
- [ ] Script bisa dipanggil: `python pipelines/daily_scoring.py`
- [ ] Menghasilkan baris di `ai_intelligence_output`
- [ ] Log tersimpan di `logs/scoring_log.csv`
- [ ] Jika QC gagal → tidak ada data baru di output table

---

### TASK-21: Unit Test Scoring & Rules
**Status**: [ ] Pending
**Dependencies**: TASK-18, TASK-19
**Output file**: `tests/test_scoring.py` dan `tests/test_rules.py`

**Instruksi untuk agent:**

`tests/test_rules.py`:
```python
1. test_self_cure_conditions()       # score=0.80, dpd=5, rate=0.90 → Self-cure
2. test_wont_pay_rejection()         # score=0.20, rejection=3 → Won't Pay
3. test_cannot_pay_broken_ptp()      # score=0.40, broken_ptp=2 → Cannot Pay
4. test_can_pay_default()            # score=0.60 → Can Pay
5. test_nba_wont_pay_high_ots()      # Won't Pay, OTS=25jt, default=2 → Pickup
6. test_nba_selfcure()               # Self-cure → WA
7. test_nba_cbs_override_up()        # NBA=WA, CBS_sensitivity=Visit → Visit
8. test_nba_no_override_down()       # NBA=Somasi, CBS_sensitivity=WA → Somasi
9. test_priority_critical()          # Won't Pay + OTS tinggi → Critical
10. test_priority_low()              # Self-cure + OTS rendah → Low
```

`tests/test_scoring.py`:
```python
1. test_recovery_score_range()       # semua score dalam [0,1]
2. test_confidence_high()            # data lengkap, score=0.90 → confidence HIGH
3. test_confidence_low_no_history()  # nasabah baru, score=0.52 → confidence LOW
4. test_qc_wont_pay_too_high()       # 35% Won't Pay → raise ValueError
```

**Acceptance Criteria:**
- [ ] `pytest tests/test_rules.py tests/test_scoring.py` → semua PASS
- [ ] Setiap test case independent (tidak bergantung order eksekusi)

---

## PHASE 6 — MLOps Feedback Loop

---

### TASK-22: Implementasi Outcome Labeler (MLOps)
**Status**: [ ] Pending
**Dependencies**: TASK-12
**Output file**: `src/outcome_labeler.py` (sudah ada, tambahkan fungsi)

**Instruksi untuk agent:**
Pastikan fungsi `label_historical_scores()` dari TASK-12 berfungsi untuk
skenario MLOps (bukan hanya training):
- Hanya label records yang `SCORING_DATE` ≥ `LABEL_WINDOW_DAYS` hari lalu
- Hanya label records yang belum ada di tabel `scoring_labels` (cek unique key)
- Append ke `scoring_labels` jika `engine` tersedia
- Return jumlah records baru yang dilabeli

Tambahkan fungsi `get_labeled_dataset(engine)` yang load semua data dari
`scoring_labels` dan join dengan contract features yang tersimpan.

**Acceptance Criteria:**
- [ ] Tidak ada double-labeling jika fungsi dipanggil 2× dalam seminggu
- [ ] Records scoring hari ini tidak dilabeli (belum bisa tahu hasilnya)
- [ ] Print: "X records baru dilabeli. Total dataset: Y records."

---

### TASK-23: Implementasi Model Monitor
**Status**: [ ] Pending
**Dependencies**: TASK-22
**Output file**: `src/model_monitor.py`

**Instruksi untuk agent:**
Implementasikan dari MLOps Pipeline Bagian 5:

**`compute_model_performance(df_labeled, window_days=30)`**:
Hitung AUC, log_loss, calibration_gap pada data `window_days` terakhir.
Return dict dengan status, metrics, dan breakdown per segment.
Return `{'status': 'insufficient_data'}` jika < 100 records.

**`compute_psi(reference_series, current_series, n_bins=10)`**:
Population Stability Index. Return float PSI value.
Handle NULL values dengan `.dropna()`.

**`run_drift_detection(df_train_snapshot, df_current_features, feature_cols)`**:
Hitung PSI untuk setiap fitur. Return (results_dict, needs_retrain_bool).
`needs_retrain = True` jika PSI critical ≥ `N_CRITICAL_DRIFT_TRIGGER` (dari settings).

**Acceptance Criteria:**
- [ ] `compute_model_performance` return dict dengan key: status, auc, calibration_gap
- [ ] `compute_psi` return 0.0 jika distribusi identik
- [ ] `compute_psi` return nilai > 0.25 pada distribusi yang sangat berbeda
- [ ] `run_drift_detection` print summary ke console

---

### TASK-24: Implementasi Champion-Challenger
**Status**: [ ] Pending
**Dependencies**: TASK-14, TASK-23
**Output file**: `src/champion_challenger.py`

**Instruksi untuk agent:**
Implementasikan dari MLOps Pipeline Bagian 7:

**`run_shadow_scoring(df_features_enriched, feature_cols, champion_path, challenger_path)`**:
Score semua kontrak dengan kedua model secara paralel.
Return DataFrame dengan kolom: CONTRACT_NO, CUST_ID, champion_score, challenger_score, score_delta, snapshot_date.
Append ke tabel `shadow_scores` jika engine tersedia.

**`evaluate_champion_vs_challenger(df_labeled, df_shadow_scores)`**:
Gabungkan labeled outcomes dengan shadow scores.
Hitung AUC untuk champion dan challenger.
Decision: PROMOTE_CHALLENGER / KEEP_CHAMPION / NO_SIGNIFICANT_DIFF.
Threshold dari settings.py: `MIN_AUC_IMPROVEMENT`.

**`promote_challenger(champion_path, challenger_path, backup_dir)`**:
Copy champion lama ke archive dengan nama berisi tanggal.
Copy challenger ke champion_path.
Update registry.
Print konfirmasi.

**Acceptance Criteria:**
- [ ] Shadow scoring tidak mengubah output operasional (hanya append ke shadow_scores)
- [ ] Evaluasi raise error jika < `MIN_SAMPLES_FOR_EVAL` records
- [ ] Promote berhasil: file champion_path setelah promote = model challenger
- [ ] Backup champion lama tersimpan di archive sebelum promote

---

### TASK-25: Implementasi Weekly MLOps Orchestrator
**Status**: [ ] Pending
**Dependencies**: TASK-22, TASK-23, TASK-24, TASK-13
**Output file**: `pipelines/weekly_mlops.py`

**Instruksi untuk agent:**
Buat `run_weekly_mlops()` yang mengorkestrasi keseluruhan MLOps flow:

```
Step 1: Label outcome baru dari scoring records lama
Step 2: Hitung performa model (AUC, calibration) pada 30 hari terakhir
Step 3: Deteksi drift pada feature distributions
Step 4: Jika perlu retrain:
           a. Ambil semua labeled data dari scoring_labels
           b. Enrich dengan feature engineering terbaru
           c. Train challenger dengan strategy_recency_weighted
           d. Simpan ke challenger_path
           e. Register ke model registry sebagai 'challenger'
Step 5: Jika ada challenger:
           a. Jalankan shadow scoring untuk hari ini
           b. Hitung berapa hari challenger sudah shadow
           c. Jika >= SHADOW_DAYS_MIN:
                - Evaluasi champion vs challenger
                - Jika PROMOTE: promote challenger, update registry
                - Hapus challenger file
Step 6: Log ke model_monitoring_log (database)
Step 7: Print ringkasan
```

**Acceptance Criteria:**
- [ ] `python pipelines/weekly_mlops.py` berjalan tanpa error
- [ ] Log tersimpan di `model_monitoring_log`
- [ ] Jika tidak ada perubahan yang diperlukan → print "No action needed"
- [ ] Jika retrain: challenger file terbuat dan ter-register

---

## PHASE 7 — Integration & End-to-End Test

---

### TASK-26: Buat Sample Data Generator
**Status**: [ ] Pending
**Dependencies**: TASK-01
**Output file**: `data/samples/generate_sample_data.py`

**Instruksi untuk agent:**
Buat script yang menghasilkan sample data realistis untuk testing:
- 100 nasabah unik di `customer_master`
- 150 kontrak (beberapa nasabah punya >1 kontrak) di `contract_snapshot`
- 500 payment records di `payment_history`
- 300 LKP records di `lkp_interaction`

Pastikan:
- Ada variasi DPD: 0–180 hari
- Ada variasi payment: Full, Partial, None
- Ada variasi PTP: dibuat dan ditepati / dilanggar
- Ada nasabah multi-kontrak (minimal 10 nasabah dengan 2+ kontrak)
- Ada nasabah dengan B_LIST kandidat (broken_ptp tinggi)
- Data mencakup minimal 6 bulan ke belakang (untuk delay_trend)

**Acceptance Criteria:**
- [ ] Script menghasilkan 4 CSV file di `data/samples/`
- [ ] Data valid (tidak ada FK yang orphan)
- [ ] Ada minimal 10% nasabah dengan 2+ kontrak aktif

---

### TASK-27: Integration Test
**Status**: [ ] Pending
**Dependencies**: TASK-26, TASK-20, TASK-15
**Output file**: `tests/test_integration.py`

**Instruksi untuk agent:**
Buat integration test yang menggunakan sample data (tidak membutuhkan database):

```python
def test_full_daily_pipeline():
    """
    Test end-to-end: dari raw data → ai_intelligence_output
    """
    # Load sample data
    # → compute features
    # → build CBS
    # → train model (dengan sample kecil)
    # → score
    # → apply rules
    # → run QC
    # Assert: output tidak kosong, semua kolom ada, tidak ada NULL di kolom wajib

def test_feedback_loop_one_cycle():
    """
    Simulasi 1 siklus feedback loop:
    1. Score kontrak (hari T)
    2. Simulasikan pembayaran (hari T+35)
    3. Label outcomes
    4. Pastikan labeled dataset terbentuk dengan benar
    """
```

**Acceptance Criteria:**
- [ ] `pytest tests/test_integration.py` → PASS dalam < 60 detik
- [ ] Test tidak membutuhkan koneksi database (gunakan DataFrame in-memory)
- [ ] Coverage semua critical path

---

### TASK-28: End-to-End Test dengan Sample Database
**Status**: [ ] Pending
**Dependencies**: TASK-27, TASK-25
**Output file**: `tests/test_e2e.py`

**Instruksi untuk agent:**
Buat E2E test menggunakan SQLite (in-memory) sebagai pengganti PostgreSQL.

Skenario yang ditest:
1. Setup schema (DDL dari TASK-03, adaptasi ke SQLite)
2. Insert sample data
3. Jalankan `run_daily_scoring()` → cek output di ai_intelligence_output
4. Simulasikan passage of time (set scoring_date = 40 hari lalu)
5. Jalankan `label_historical_scores()` → cek scoring_labels terisi
6. Jalankan `compute_model_performance()` → pastikan ada AUC
7. Jalankan drift detection
8. Jalankan `run_weekly_mlops()` → pastikan tidak error

**Acceptance Criteria:**
- [ ] Keseluruhan skenario selesai tanpa exception
- [ ] `scoring_labels` terisi setelah labeling
- [ ] `model_monitoring_log` memiliki entry setelah weekly MLOps
- [ ] Tidak ada data leak antar test (setiap test pakai DB fresh)

---

### TASK-29: Setup Scheduler
**Status**: [ ] Pending
**Dependencies**: TASK-20, TASK-25
**Output file**: `config/cron_setup.sh`

**Instruksi untuk agent:**
Buat file `config/cron_setup.sh` berisi instruksi cron untuk:

```bash
#!/bin/bash
# Setup cron jobs untuk CollectAI
# Jalankan: bash config/cron_setup.sh

PROJECT_DIR="/path/to/collectai"
PYTHON="/usr/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"

# Daily scoring: setiap malam jam 23:00
DAILY_CRON="0 23 * * * cd $PROJECT_DIR && $PYTHON pipelines/daily_scoring.py >> $LOG_DIR/daily.log 2>&1"

# Weekly MLOps: setiap Senin jam 06:00
WEEKLY_CRON="0 6 * * 1 cd $PROJECT_DIR && $PYTHON pipelines/weekly_mlops.py >> $LOG_DIR/weekly.log 2>&1"

# Daftarkan ke crontab
(crontab -l 2>/dev/null; echo "$DAILY_CRON") | crontab -
(crontab -l 2>/dev/null; echo "$WEEKLY_CRON") | crontab -

echo "Cron jobs registered successfully."
crontab -l
```

Sertakan juga contoh Airflow DAG sebagai alternatif (`config/airflow_dag.py`).

**Acceptance Criteria:**
- [ ] `bash config/cron_setup.sh` berhasil (tidak error)
- [ ] `crontab -l` menampilkan 2 jobs baru
- [ ] Airflow DAG bisa di-import tanpa error

---

### TASK-30: Dokumentasi README
**Status**: [ ] Pending
**Dependencies**: Semua task sebelumnya
**Output file**: `README.md`

**Instruksi untuk agent:**
Tulis README.md yang mencakup:

1. **Overview**: Apa itu CollectAI dan apa yang dilakukannya
2. **Architecture Diagram** (ASCII): 4 tabel input → feature engineering → AI engine → 2 output
3. **Quick Start**: langkah install dan jalankan sistem dari nol
4. **File Structure**: penjelasan singkat setiap file/folder
5. **Configuration**: cara mengubah threshold di settings.py
6. **Schedules**: kapan apa dijalankan
7. **Model Retraining**: kapan dan bagaimana model diperbarui otomatis
8. **Troubleshooting**: 5 error umum dan cara mengatasinya

**Acceptance Criteria:**
- [ ] README bisa dibaca oleh developer baru yang belum kenal sistem ini
- [ ] Quick Start bisa diikuti dari nol hingga first scoring tanpa membuka file lain
- [ ] Semua referensi ke file yang ada benar (tidak ada typo path)

---

## RINGKASAN EKSEKUSI

```
TOTAL TASK   : 30 tasks
TOTAL PHASE  : 7 phases

Urutan minimum untuk first working scoring:
  T01 → T02 → T03 → T04 → T05 → T07 → T09 → T10 → T12 →
  T13 → T14 → T15 → T16 → T17 → T18 → T19 → T20

Urutan untuk sistem self-improving:
  + T22 → T23 → T24 → T25

Urutan untuk production-ready:
  + T08 → T11 → T21 → T26 → T27 → T28 → T29 → T30

Dependency kritis yang tidak boleh dilewati:
  T05 (contract features) HARUS selesai sebelum T07 (enrich)
  T09 (CBS rules)         HARUS selesai sebelum T10 (CBS update)
  T15 (initial training)  HARUS selesai sebelum T16 (scoring)
  T15 (champion exists)   HARUS selesai sebelum T20 (daily runner)
```