# CollectAI — Analisis Data Tambahan & Upgrade Task List
> Dokumen ini mengevaluasi 19 field usulan dari tim, memutuskan mana yang
> ditambahkan dan mana yang diabaikan, lalu menyusun task upgrade untuk AI agent.
> Diasumsikan TASK-01 sampai TASK-30 sudah selesai dikerjakan.

---

## BAGIAN 1 — ANALISIS FIELD PER FIELD

### Kerangka Penilaian

Setiap field dinilai berdasarkan tiga kriteria:
- **Signal Value**: apakah field ini membawa informasi baru yang belum ada di sistem?
- **Inference Replacement**: apakah field ini menggantikan sesuatu yang selama ini kita infer (tebak) dari data lain?
- **Operational Impact**: apakah field ini mengubah keputusan NBA atau CBS secara berarti?

---

### CONTRACT SNAPSHOT (10 field usulan)

| Field | Keputusan | Alasan |
|---|---|---|
| `AMBC` | ✅ **TAMBAHKAN** | Amount Must Be Collected = jumlah MINIMUM yang harus dibayar sekarang agar kontrak tidak memburuk. Berbeda dari OTS yang adalah total saldo. Feature baru: `ambc_to_ots_ratio` — semakin kecil rasio ini, semakin kecil beban segera. Langsung mengubah NBA calculation. |
| `SNAPSHOT_DATE` | ❌ **ABAIKAN** | Infrastructure field. Pipeline kita sudah menggunakan `reference_date` sebagai tanggal scoring. Tidak membawa signal prediktif apapun. Menambah kolom tanpa manfaat. |
| `PREV_CYCLE` | ✅ **TAMBAHKAN — PRIORITAS TINGGI** | Ini adalah salah satu tambahan paling berharga. Dua nasabah sama-sama di C2 hari ini: yang pertama bulan lalu C1 (memburuk), yang kedua bulan lalu C3 (membaik). Perilaku mereka sangat berbeda. Feature baru: `cycle_direction` = cycle_encoded − prev_cycle_encoded. Positif = memburuk, negatif = membaik. Juga menjadi training label untuk **Roll Forward sub-model**. |
| `LOAN_AMOUNT` | ✅ **TAMBAHKAN** | Memungkinkan perhitungan `recovery_ratio` = (LOAN_AMOUNT − total_ots) / LOAN_AMOUNT. Nasabah yang sudah melunasi 80% pinjaman vs baru 10% sangat berbeda perilakunya saat terlambat. Track record pembayaran historis dalam satu angka. |
| `TENOR_MONTH` | ❌ **ABAIKAN** | Kita sudah punya `MATURITY_DATE`. `remaining_tenor_months` = (MATURITY_DATE − TODAY) / 30 jauh lebih informatif dari tenor original yang tidak berubah. Tenor asal tidak membawa signal perilaku — yang penting adalah sisa waktu, bukan durasi total. |
| `INSTALLMENT_AMOUNT` | ✅ **TAMBAHKAN** | Memungkinkan `installment_to_income_ratio` = INSTALLMENT_AMOUNT / income_proxy. Lebih presisi dari hanya pakai INCOME_LEVEL kategorikal. Nasabah dengan cicilan 60% dari pendapatan jauh lebih rentan shock finansial. Model bisa belajar ini. |
| `INTEREST_RATE` | ❌ **ABAIKAN** | Interest rate di-set saat origination dan tidak berubah sepanjang kontrak. Bukan signal perilaku. Pola risikonya sudah largely captured oleh PRODUCT_TYPE dan total_ots. Menambah dimensi tanpa nilai prediktif inkremental yang signifikan. |
| `MATURITY_DATE` | ✅ **TAMBAHKAN — PRIORITAS TINGGI** | Feature baru: `days_to_maturity`. Nasabah yang kontraknya tinggal 30 hari sangat berbeda dari yang masih 3 tahun — near-maturity nasabah cenderung self-cure karena tidak mau kredit macet di penutupan kontrak. NBA: kontrak near-maturity dengan OTS kecil → WA saja, jangan visit. |
| `OVERDUE_INSTALLMENT_COUNT` | ✅ **TAMBAHKAN** | Lebih granular dari DPD untuk produk cicilan bulanan. DPD 45 bisa berarti 1 atau 2 angsuran menunggak tergantung tanggal jatuh tempo. Field ini langsung menunjukkan "berapa cicilan yang harus dikejar nasabah untuk catch up". Berguna untuk framing negosiasi collector. |
| `LATE_FEE_AMOUNT` | ✅ **TAMBAHKAN** | Proxy akumulatif untuk riwayat keterlambatan. Late fee tinggi = bukan hanya terlambat sekarang, tapi pola berulang. Juga berguna untuk NBA: nasabah dengan late fee besar mungkin mau bayar jika ditawarkan fee waiver sebagai insentif — tactic yang bisa dimasukkan ke script collector. |

---

### LKP & INTERACTION (4 field usulan)

| Field | Keputusan | Alasan |
|---|---|---|
| `PTP_AMOUNT` | ✅ **TAMBAHKAN — PRIORITAS TINGGI** | Saat ini kita tahu PTP dibuat tapi tidak tahu untuk berapa besar. Feature baru: `ptp_coverage_ratio` = PTP_AMOUNT / AMBC. Nasabah yang janji bayar 100% AMBC vs 20% AMBC sangat berbeda reliabilitasnya. Juga sinyal niat: apakah janji ini realistis? |
| `PTP_STATUS` | ✅ **TAMBAHKAN — PRIORITAS SANGAT TINGGI** | Ini menggantikan sesuatu yang sekarang kita INFER. Saat ini `ptp_fulfillment_rate` dihitung dengan cek "ada pembayaran dalam 7 hari setelah PROMISE_DATE" — pendekatan heuristic yang tidak akurat. Dengan PTP_STATUS (OPEN/KEPT/BROKEN), kita punya label langsung. Lebih akurat, lebih simple, dan menjadi training label untuk **PTP Success sub-model**. `broken_ptp_count` kini dihitung langsung: `COUNT(PTP_STATUS='BROKEN')`. |
| `RPC_FLAG` | ✅ **TAMBAHKAN — PRIORITAS TINGGI** | Right Party Contact: apakah kita benar-benar berbicara dengan nasabahnya, bukan keluarga atau tetangga? Feature baru: `rpc_rate` = COUNT(RPC=True) / COUNT(all attempts). RPC rate rendah → nasabah sulit dihubungi langsung → NBA: Visit untuk establish direct contact. Sangat berguna untuk segmen Won't Pay dimana contact quality sangat menentukan. |
| `CONTACT_SUCCESS_FLAG` | ✅ **TAMBAHKAN** | Berbeda dari RPC: CONTACT_SUCCESS = berhasil menghubungi siapapun. RPC = berhasil menghubungi nasabah yang tepat. Kombinasi keduanya memberi gambaran lengkap: apakah nomor masih aktif? Apakah ada yang angkat? Apakah yang angkat adalah orangnya? Feature: `contact_success_rate`. NBA: nasabah dengan contact_success_rate < 20% → alamat perlu diverifikasi via Visit. |

---

### PAYMENT HISTORY (2 field usulan)

| Field | Keputusan | Alasan |
|---|---|---|
| `SELF_CURE_FLAG` | ✅ **TAMBAHKAN — PRIORITAS SANGAT TINGGI** | Saat ini kita infer self-cure dari "tidak ada LKP dalam 7 hari sebelum pembayaran" — pendekatan sangat kasar. Dengan flag langsung, kita tahu pasti: nasabah ini bayar sendiri tanpa dipicu collector. Ini menjadi training label untuk **Self-cure sub-model** yang akan menghasilkan `SELF_CURE_PROBABILITY`. Dampak operasional besar: nasabah dengan SELF_CURE_PROBABILITY tinggi tidak perlu di-assign ke collector → hemat cost signifikan. |
| `RECOVERY_SOURCE` | ✅ **TAMBAHKAN — PRIORITAS SANGAT TINGGI** | Saat ini `channel_effectiveness` di CBS kita infer: "TREATMENT_TYPE apa yang paling sering mendahului pembayaran dalam beberapa hari". Ini heuristic dengan banyak false attribution. Dengan RECOVERY_SOURCE, kita tahu LANGSUNG: pembayaran ini terjadi karena channel X. CBS field `COLLECTION_SENSITIVITY` menjadi jauh lebih akurat. Eliminasi inference, gunakan ground truth. |

---

### AI INTELLIGENCE OUTPUT (3 field usulan)

| Field | Keputusan | Alasan |
|---|---|---|
| `SELF_CURE_PROBABILITY` | ✅ **TAMBAHKAN** | Output dari Self-cure sub-model. Nasabah dengan nilai ini > 0.70 tidak perlu diassign ke collector — bayar sendiri. Transformasi operasional: collector bisa fokus 100% ke kontrak yang benar-benar butuh intervensi. |
| `ROLL_FORWARD_RISK` | ✅ **TAMBAHKAN — PRIORITAS TINGGI** | Output dari Roll Forward sub-model. RECOVERY_SCORE dan ROLL_FORWARD_RISK memberikan dua dimensi berbeda: nasabah bisa RECOVERY_SCORE=0.60 (mungkin akhirnya bayar) tapi ROLL_FORWARD_RISK=0.85 (kalau tidak ditagih minggu ini, bulan depan masuk bucket lebih buruk). Ini mengubah urgency. Priority matrix perlu disesuaikan untuk incorporate dimensi ini. |
| `PTP_SUCCESS_PROBABILITY` | ✅ **TAMBAHKAN** | Output dari PTP Success sub-model. Berguna saat collector sedang negosiasi: jika model memprediksi PTP_SUCCESS < 0.30, collector tidak perlu terima janji bayar — push untuk partial payment langsung. Mengubah cara collector bekerja dari reaktif ke informed. |

---

### RINGKASAN KEPUTUSAN

```
✅ TAMBAHKAN (14 field):
   Contract Snapshot : AMBC, PREV_CYCLE, LOAN_AMOUNT, INSTALLMENT_AMOUNT,
                       MATURITY_DATE, OVERDUE_INSTALLMENT_COUNT, LATE_FEE_AMOUNT
   LKP Interaction   : PTP_AMOUNT, PTP_STATUS, RPC_FLAG, CONTACT_SUCCESS_FLAG
   Payment History   : SELF_CURE_FLAG, RECOVERY_SOURCE
   AI Output         : SELF_CURE_PROBABILITY, ROLL_FORWARD_RISK, PTP_SUCCESS_PROBABILITY

❌ ABAIKAN (5 field):
   Contract Snapshot : SNAPSHOT_DATE (infrastructure field, tidak ada signal)
                       TENOR_MONTH   (redundant, MATURITY_DATE lebih informatif)
                       INTEREST_RATE (bukan signal perilaku, captured by PRODUCT_TYPE)
```

---

### Dampak Sistemik dari Penambahan Ini

```
SEBELUM penambahan:
  Sistem punya 1 model output: RECOVERY_SCORE
  CBS menggunakan 3 inference heuristics:
    - ptp_fulfillment dihitung dari payment window
    - channel_effectiveness dihitung dari treatment-payment proximity
    - broken_ptp_count dihitung dari absence of payment after PTP

SETELAH penambahan:
  Sistem punya 4 model output: RECOVERY_SCORE + SELF_CURE_PROB +
                                ROLL_FORWARD_RISK + PTP_SUCCESS_PROB
  CBS menggunakan 0 inference heuristics:
    - ptp_fulfillment langsung dari PTP_STATUS='KEPT'/'BROKEN'
    - channel_effectiveness langsung dari RECOVERY_SOURCE
    - broken_ptp_count langsung dari COUNT(PTP_STATUS='BROKEN')
  
  New contract features: +8 features (dari 13 → 21 contract-level features)
  New customer features: +4 features (rpc_rate, contact_success_rate,
                                       self_cure_rate, ptp_coverage_ratio)
  Total FEATURE_COLS: dari 21 → 29 features
```

---

## BAGIAN 2 — UPGRADE TASK LIST

> Task-task berikut adalah lanjutan dari TASK-01 s/d TASK-30 yang sudah selesai.
> Kerjakan secara berurutan dalam tiap phase.

---

## PHASE 8 — Schema & Config Upgrade

---

### TASK-31: Update Database Schema
**Status**: [ ] Pending
**Dependencies**: TASK-03 (schema awal sudah ada)
**Output file**: `config/schema_v2.sql`

**Instruksi untuk agent:**
Buat file `config/schema_v2.sql` berisi ALTER TABLE statements untuk
menambahkan kolom baru ke tabel yang sudah ada, TANPA menghapus kolom lama.

```sql
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

-- ── NEW INDEXES ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_lkp_ptp_status
  ON lkp_interaction (contract_no, ptp_status);
CREATE INDEX IF NOT EXISTS idx_payment_self_cure
  ON payment_history (contract_no, self_cure_flag);
CREATE INDEX IF NOT EXISTS idx_payment_recovery_source
  ON payment_history (recovery_source);
```

**Acceptance Criteria:**
- [ ] Semua ALTER TABLE berjalan tanpa error (termasuk pada tabel yang sudah berisi data)
- [ ] `IF NOT EXISTS` digunakan di semua ADD COLUMN (idempotent — aman dijalankan ulang)
- [ ] CHECK constraints untuk PTP_STATUS dan RECOVERY_SOURCE berfungsi
- [ ] Kolom lama (dari schema v1) tidak berubah

---

### TASK-32: Update `config/settings.py`
**Status**: [ ] Pending
**Dependencies**: TASK-31
**Output file**: `config/settings.py` (update file yang sudah ada)

**Instruksi untuk agent:**
Update `config/settings.py` dengan menambahkan konstanta baru dan
memperbarui `FEATURE_COLS`. Jangan hapus konstanta lama.

Tambahan yang harus ada:

```python
# ── FEATURE COLS BARU (ganti yang lama seluruhnya) ────────────────
FEATURE_COLS = [
    # Contract-level LAMA (13 features — tetap ada)
    "DPD_CURRENT", "cycle_encoded", "total_ots",
    "payment_rate", "partial_rate", "avg_delay_days",
    "days_since_last_pay", "ptp_fulfillment_rate",
    "avg_interaction_score", "last_result_code_encoded",
    "treatment_count", "rejection_count", "payment_count",

    # Contract-level BARU (8 features — tambahan)
    "ambc", "ambc_to_ots_ratio", "prev_cycle_encoded",
    "cycle_direction", "days_to_maturity", "recovery_ratio",
    "installment_to_income_ratio", "overdue_installment_count",
    "late_fee_amount",

    # LKP-level BARU (4 features)
    "rpc_rate", "contact_success_rate",
    "ptp_coverage_ratio", "open_ptp_count",

    # Payment-level BARU (2 features)
    "self_cure_rate", "recovery_source_encoded",

    # Customer-level dari CBS (8 features — tetap ada)
    "ptp_reliability_index", "delay_trend",
    "historical_default_count", "income_debt_ratio",
    "active_contract_count", "total_active_ots",
    "behavioral_grade_encoded", "b_list_flag",
]

# ── FEATURE COLS PER SUB-MODEL ────────────────────────────────────
# Sub-model mungkin butuh subset fitur yang berbeda

SELF_CURE_FEATURE_COLS = [
    # Self-cure lebih dipengaruhi oleh karakter nasabah,
    # bukan seberapa keras kita menagih
    "DPD_CURRENT", "cycle_encoded", "days_to_maturity",
    "payment_rate", "avg_delay_days", "self_cure_rate",
    "ptp_reliability_index", "behavioral_grade_encoded",
    "recovery_ratio", "installment_to_income_ratio",
    "ambc", "ambc_to_ots_ratio",
]

ROLL_FORWARD_FEATURE_COLS = [
    # Roll forward sangat dipengaruhi oleh posisi dan arah saat ini
    "DPD_CURRENT", "cycle_encoded", "prev_cycle_encoded",
    "cycle_direction", "ambc", "ambc_to_ots_ratio",
    "overdue_installment_count", "payment_rate",
    "avg_delay_days", "days_to_maturity",
    "total_ots", "income_debt_ratio",
    "contact_success_rate", "rpc_rate",
]

PTP_SUCCESS_FEATURE_COLS = [
    # PTP success lebih dipengaruhi oleh behavior LKP
    "ptp_coverage_ratio", "ptp_reliability_index",
    "avg_interaction_score", "rpc_rate",
    "contact_success_rate", "behavioral_grade_encoded",
    "DPD_CURRENT", "cycle_encoded", "ambc",
    "b_list_flag", "broken_ptp_count",
]

# ── PATH SUB-MODELS ───────────────────────────────────────────────
SELF_CURE_MODEL_PATH    = "models/self_cure_model.pkl"
ROLL_FORWARD_MODEL_PATH = "models/roll_forward_model.pkl"
PTP_SUCCESS_MODEL_PATH  = "models/ptp_success_model.pkl"

# ── THRESHOLDS BARU ───────────────────────────────────────────────
SELF_CURE_PROB_THRESHOLD    = 0.70  # di atas ini → tidak perlu assign collector
ROLL_FORWARD_HIGH_RISK      = 0.75  # di atas ini → naikkan priority satu level
PTP_SUCCESS_LOW_THRESHOLD   = 0.30  # di bawah ini → push for immediate payment

DAYS_TO_MATURITY_SHORT      = 60    # kontrak sisa < 60 hari = near-maturity
LATE_FEE_WAIVER_THRESHOLD   = 500_000  # late fee di atas ini → eligible waiver offer

# ── RPC CONFIG ────────────────────────────────────────────────────
RPC_RATE_LOW_THRESHOLD      = 0.30  # RPC < 30% → butuh Visit untuk direct contact
CONTACT_SUCCESS_LOW         = 0.20  # Contact < 20% → perlu verifikasi alamat
```

**Acceptance Criteria:**
- [ ] `FEATURE_COLS` memiliki tepat 29 items (13 lama + 8 contract baru + 4 LKP + 2 payment + 8 CBS -- no double count)

    Wait, let me count: 13 (contract lama) + 8 (contract baru) = 21 contract features. Wait the FEATURE_COLS above has:
    - 13 contract lama
    - 9 contract baru (ambc, ambc_to_ots_ratio, prev_cycle_encoded, cycle_direction, days_to_maturity, recovery_ratio, installment_to_income_ratio, overdue_installment_count, late_fee_amount)
    - 4 LKP baru (rpc_rate, contact_success_rate, ptp_coverage_ratio, open_ptp_count)
    - 2 payment baru (self_cure_rate, recovery_source_encoded)
    - 8 customer CBS (ptp_reliability_index, delay_trend, historical_default_count, income_debt_ratio, active_contract_count, total_active_ots, behavioral_grade_encoded, b_list_flag)
    Total = 13+9+4+2+8 = 36 features. Let me update the acceptance criteria.

- [ ] `FEATURE_COLS` total = 36 items (dari 21 sebelumnya)
- [ ] `from config.settings import SELF_CURE_MODEL_PATH` berhasil
- [ ] Semua path model baru terdefinisi

---

## PHASE 9 — Feature Engineering Upgrade

---

### TASK-33: Update Contract-Level Feature Engineering
**Status**: [ ] Pending
**Dependencies**: TASK-32, TASK-05 (versi lama sudah ada)
**Output file**: `src/feature_engineering.py` (update fungsi `compute_contract_features`)

**Instruksi untuk agent:**
Update fungsi `compute_contract_features()` yang sudah ada di TASK-05.
Tambahkan 9 fitur baru tanpa menghapus 13 fitur lama.

**9 Fitur baru yang harus ditambahkan:**

```python
# ── DARI AMBC ─────────────────────────────────────────────────────
features['ambc'] = cs['AMBC'].fillna(cs['total_ots'])
# Jika AMBC NULL (data lama), fallback ke total_ots

features['ambc_to_ots_ratio'] = (
    features['ambc'] / features['total_ots'].replace(0, np.nan)
).clip(0, 1)
# Clip ke 1 karena AMBC tidak seharusnya > OTS

# ── DARI PREV_CYCLE ───────────────────────────────────────────────
CYCLE_MAP = {'C0': 0, 'C1': 1, 'C2': 2, 'C3': 3}
features['prev_cycle_encoded'] = (
    cs['PREV_CYCLE'].map(CYCLE_MAP).fillna(features['cycle_encoded'])
)
# Jika PREV_CYCLE NULL → asumsi sama dengan current (no change)

features['cycle_direction'] = (
    features['cycle_encoded'] - features['prev_cycle_encoded']
)
# Positif = memburuk (roll forward), Negatif = membaik, 0 = stabil

# ── DARI MATURITY_DATE ────────────────────────────────────────────
features['days_to_maturity'] = (
    (pd.to_datetime(cs['MATURITY_DATE']) - pd.to_datetime(reference_date))
    .dt.days
    .clip(lower=0)
)
# Clip ke 0 — kontrak yang sudah lewat maturity = 0 hari tersisa

# ── DARI LOAN_AMOUNT ──────────────────────────────────────────────
features['recovery_ratio'] = (
    (cs['LOAN_AMOUNT'] - features['total_ots'])
    / cs['LOAN_AMOUNT'].replace(0, np.nan)
).clip(0, 1)
# 0.0 = belum bayar sama sekali, 1.0 = sudah lunas penuh

# ── DARI INSTALLMENT_AMOUNT ───────────────────────────────────────
features['installment_to_income_ratio'] = (
    cs['INSTALLMENT_AMOUNT']
    / cs['CUST_ID'].map(income_proxy_map)  # dari lookup customer master
).clip(0, 5)
# Clip ke 5 (500% dari income) untuk menghindari outlier ekstrem

# ── DARI OVERDUE_INSTALLMENT_COUNT ───────────────────────────────
features['overdue_installment_count'] = (
    cs['OVERDUE_INSTALLMENT_COUNT'].fillna(0)
)

# ── DARI LATE_FEE_AMOUNT ──────────────────────────────────────────
features['late_fee_amount'] = (
    cs['LATE_FEE_AMOUNT'].fillna(0)
)
```

**Catatan penting — handle data lama tanpa field baru:**
Jika data historis tidak memiliki field baru (misal AMBC = NULL untuk semua record lama),
gunakan fallback yang masuk akal:
- `ambc` → fallback ke `total_ots`
- `prev_cycle_encoded` → fallback ke `cycle_encoded` (no change)
- `days_to_maturity` → fallback ke 365 (asumsi masih lama)
- `recovery_ratio` → fallback ke NULL
- `overdue_installment_count` → fallback ke 0
- `late_fee_amount` → fallback ke 0

**Acceptance Criteria:**
- [ ] Fungsi tetap menghasilkan 13 fitur lama PLUS 9 fitur baru (total 22 contract features)
- [ ] `cycle_direction` berisi nilai -3 hingga +3
- [ ] `days_to_maturity` tidak pernah negatif (di-clip ke 0)
- [ ] `ambc_to_ots_ratio` dalam range [0, 1]
- [ ] Tidak ada error jika field baru NULL (semua ada fallback)
- [ ] Test: kontrak dari C1 ke C2 → `cycle_direction = 1` (memburuk)
- [ ] Test: kontrak dari C2 ke C1 → `cycle_direction = -1` (membaik)

---

### TASK-34: Update LKP Feature Engineering
**Status**: [ ] Pending
**Dependencies**: TASK-33, TASK-05
**Output file**: `src/feature_engineering.py` (update bagian LKP features)

**Instruksi untuk agent:**
Update bagian LKP dalam `compute_contract_features()`.
Tambahkan 4 fitur baru dan **ubah cara menghitung `ptp_fulfillment_rate`**.

**Perubahan pada `ptp_fulfillment_rate` (BREAKING CHANGE dari TASK-05):**
```python
# LAMA (inference dari payment window — HAPUS):
# ptp_rows['ptp_kept'] = (ACTUAL_PAY_DATE dalam PTP_DAYS_WINDOW setelah PROMISE_DATE)

# BARU (direct dari PTP_STATUS jika tersedia):
if 'PTP_STATUS' in lkp.columns and lkp['PTP_STATUS'].notna().any():
    # Gunakan PTP_STATUS langsung
    ptp_agg = lkp[lkp['RESULT_CODE'] == 'PTP'].groupby('CONTRACT_NO').agg(
        total_ptp_made  = ('LKP_ID', 'count'),
        total_ptp_kept  = ('PTP_STATUS', lambda x: (x == 'KEPT').sum()),
        open_ptp_count  = ('PTP_STATUS', lambda x: (x == 'OPEN').sum()),
    ).reset_index()
else:
    # Fallback ke inference lama jika PTP_STATUS belum ada
    # (untuk backward compatibility dengan data historis)
    ptp_agg = compute_ptp_from_payment_window(...)  # fungsi lama
    ptp_agg['open_ptp_count'] = 0

ptp_agg['ptp_fulfillment_rate'] = (
    ptp_agg['total_ptp_kept']
    / ptp_agg['total_ptp_made'].replace(0, np.nan)
)
```

**4 Fitur baru dari LKP:**
```python
# rpc_rate: berapa % kontak yang berhasil reach right party
lkp_agg['rpc_rate'] = (
    lkp.groupby('CONTRACT_NO')['RPC_FLAG']
    .mean()  # True=1, False=0, mean = proportion
    .fillna(0)
)

# contact_success_rate: berapa % upaya kontak yang berhasil terhubung
lkp_agg['contact_success_rate'] = (
    lkp.groupby('CONTRACT_NO')['CONTACT_SUCCESS_FLAG']
    .mean()
    .fillna(0)
)

# ptp_coverage_ratio: total PTP_AMOUNT vs AMBC
# (apakah nasabah berjanji untuk jumlah yang cukup?)
ptp_sum = (
    lkp[lkp['RESULT_CODE'] == 'PTP']
    .groupby('CONTRACT_NO')['PTP_AMOUNT']
    .sum()
)
# Merge ke features lalu hitung
features['ptp_coverage_ratio'] = (
    ptp_sum / features['ambc'].replace(0, np.nan)
).clip(0, 2)  # clip ke 2× AMBC

# open_ptp_count: sudah dihitung di atas dari PTP_STATUS
features['open_ptp_count'] = ptp_agg['open_ptp_count'].fillna(0)
```

**Acceptance Criteria:**
- [ ] `ptp_fulfillment_rate` menggunakan PTP_STATUS jika tersedia, fallback jika tidak
- [ ] `rpc_rate` dalam range [0.0, 1.0]
- [ ] `contact_success_rate` dalam range [0.0, 1.0]
- [ ] `ptp_coverage_ratio` di-clip ke [0, 2]
- [ ] Test: 3 PTP dibuat, 2 KEPT, 1 BROKEN → `ptp_fulfillment_rate = 0.667`
- [ ] Test: 5 kontak, 3 RPC_FLAG=True → `rpc_rate = 0.6`

---

### TASK-35: Update Payment History Features
**Status**: [ ] Pending
**Dependencies**: TASK-33
**Output file**: `src/feature_engineering.py` (update bagian payment features)

**Instruksi untuk agent:**
Update bagian payment history dalam `compute_contract_features()`.
Tambahkan 2 fitur baru dan **ubah cara menghitung `channel_effectiveness` di customer features**.

```python
# ── SELF_CURE_RATE ────────────────────────────────────────────────
# Berapa % pembayaran yang dilakukan sendiri tanpa intervensi collector
if 'SELF_CURE_FLAG' in pay.columns:
    pay_agg['self_cure_rate'] = (
        pay.groupby('CONTRACT_NO')['SELF_CURE_FLAG']
        .mean()
        .fillna(0)
    )
else:
    pay_agg['self_cure_rate'] = np.nan  # tidak bisa hitung jika data belum ada

# ── RECOVERY_SOURCE_ENCODED ───────────────────────────────────────
# Channel yang paling sering menghasilkan pembayaran untuk kontrak ini
RECOVERY_SOURCE_MAP = {
    'WA': 1, 'SMS': 2, 'Deskcoll': 3, 'Visit': 4, 'Somasi': 5
}
if 'RECOVERY_SOURCE' in pay.columns:
    # Mode (channel yang paling sering muncul) untuk kontrak ini
    most_effective = (
        pay[pay['RECOVERY_SOURCE'].notna()]
        .groupby('CONTRACT_NO')['RECOVERY_SOURCE']
        .agg(lambda x: x.mode()[0] if len(x) > 0 else None)
    )
    pay_agg['recovery_source_encoded'] = (
        most_effective.map(RECOVERY_SOURCE_MAP).fillna(0)
    )
else:
    pay_agg['recovery_source_encoded'] = 0
```

**Update `compute_customer_features()` — ubah `channel_effectiveness`:**
```python
# LAMA (inference):
# channel_effectiveness = MODE(TREATMENT_TYPE WHERE setelah LKP ada pembayaran)

# BARU (direct):
if 'RECOVERY_SOURCE' in pay.columns:
    channel_eff = (
        pay[pay['RECOVERY_SOURCE'].notna()]
        .groupby('CUST_ID_via_contract')['RECOVERY_SOURCE']
        .agg(lambda x: x.mode()[0] if len(x) > 0 else None)
    )
    customer_features['channel_effectiveness'] = channel_eff
    # Tidak perlu lagi inference dari TREATMENT_TYPE proximity
```

**Acceptance Criteria:**
- [ ] `self_cure_rate` dalam range [0.0, 1.0] atau NULL jika belum ada data
- [ ] `recovery_source_encoded` dalam range [0, 5]
- [ ] `channel_effectiveness` di CBS sekarang dari RECOVERY_SOURCE, bukan inference LKP proximity
- [ ] Backward compatible: jika kolom baru NULL di data historis → nilai default, bukan error

---

### TASK-36: Update CBS Builder
**Status**: [ ] Pending
**Dependencies**: TASK-34, TASK-35, TASK-09
**Output file**: `src/cbs_builder.py` (update fungsi yang sudah ada)

**Instruksi untuk agent:**
Update `build_cbs()` untuk memanfaatkan data baru yang lebih akurat.
Tiga perubahan utama:

**1. `broken_ptp_count` — dari inference ke direct count:**
```python
# LAMA: broken = total_ptp_made - total_ptp_kept (dihitung dari payment window)
# BARU: langsung dari COUNT(PTP_STATUS='BROKEN') per CUST_ID lintas kontrak
if 'ptp_status' in df_lkp.columns:
    broken_ptp = (
        df_lkp[df_lkp['ptp_status'] == 'BROKEN']
        .groupby('cust_id_via_contract')
        .size()
        .reset_index(name='broken_ptp_count')
    )
```

**2. `ptp_reliability_index` — lebih akurat:**
```python
# BARU: langsung dari PTP_STATUS per CUST_ID
ptp_stats = df_lkp[df_lkp['result_code'] == 'PTP'].groupby('cust_id').agg(
    total_ptp_made = ('lkp_id', 'count'),
    total_ptp_kept = ('ptp_status', lambda x: (x == 'KEPT').sum()),
).reset_index()
ptp_stats['ptp_reliability_index'] = (
    ptp_stats['total_ptp_kept']
    / ptp_stats['total_ptp_made'].replace(0, np.nan)
)
```

**3. `channel_effectiveness` — dari RECOVERY_SOURCE:**
```python
# BARU: gunakan RECOVERY_SOURCE langsung dari payment_history
channel_eff = (
    df_payment[df_payment['recovery_source'].notna()]
    .groupby('cust_id')['recovery_source']
    .agg(lambda x: x.mode()[0] if len(x) > 0 else None)
)
cbs['collection_sensitivity'] = channel_eff
```

**Acceptance Criteria:**
- [ ] `broken_ptp_count` menggunakan PTP_STATUS='BROKEN' jika tersedia
- [ ] `ptp_reliability_index` lebih akurat (tidak bergantung payment window heuristic)
- [ ] `channel_effectiveness` menggunakan RECOVERY_SOURCE jika tersedia
- [ ] Backward compatible: fallback ke metode lama jika kolom baru belum ada

---

## PHASE 10 — Sub-Model Training

> Sistem sekarang memiliki 4 model terpisah.
> Masing-masing menjawab pertanyaan bisnis yang berbeda.

```
MODEL                  │ PERTANYAAN                              │ TRAINING LABEL
───────────────────────┼─────────────────────────────────────────┼──────────────────────
Recovery Scoring       │ Apakah nasabah akan bayar dalam 30 hari?│ actual_paid (0/1)
Self-cure Sub-model    │ Apakah nasabah akan bayar SENDIRI?      │ actual_self_cure (0/1)
Roll Forward Sub-model │ Apakah cycle akan memburuk bulan ini?   │ actual_roll_forward (0/1)
PTP Success Sub-model  │ Apakah PTP ini akan ditepati?           │ actual_ptp_kept (0/1)
```

---

### TASK-37: Retrain Main Recovery Model dengan Feature Baru
**Status**: [ ] Pending
**Dependencies**: TASK-33, TASK-34, TASK-35, TASK-36, TASK-13
**Output file**: `models/recovery_model_champion.pkl` (updated)

**Instruksi untuk agent:**
Retrain model Recovery Score dengan dataset yang sudah diperkaya 36 features.
Ini adalah **Champion v2** — menggantikan v1 dari TASK-15.

1. Jalankan ulang feature engineering dengan FEATURE_COLS baru (36 features)
2. Build target variable (sama: `actual_paid_within_30d`)
3. Train dengan `strategy_recency_weighted()` yang sudah ada
4. Bandingkan CV AUC dengan Champion v1 — expected lebih tinggi karena lebih banyak fitur
5. Jika AUC naik → promote langsung sebagai champion baru (tidak perlu shadow karena ini upgrade terencana)
6. Update registry

**Acceptance Criteria:**
- [ ] Model artifact berisi 36 features di `feature_cols`
- [ ] CV AUC ≥ Champion v1 (jika tidak, investigasi feature yang bermasalah)
- [ ] `training_features_sample` diperbarui dengan distribusi 36 features baru
- [ ] Registry menunjukkan v2 sebagai champion aktif

---

### TASK-38: Build Self-Cure Sub-Model
**Status**: [ ] Pending
**Dependencies**: TASK-33, TASK-35, TASK-12
**Output file**: `models/self_cure_model.pkl`

**Instruksi untuk agent:**
Bangun sub-model yang memprediksi apakah nasabah akan bayar **tanpa** intervensi collector.

**Mendefinisikan training label:**
```python
def build_self_cure_label(df_features, df_payment, scoring_date, n_days=30):
    """
    Target: actual_self_cure = 1 jika:
      - Ada pembayaran dalam 30 hari (actual_paid = 1) DAN
      - SELF_CURE_FLAG = True pada pembayaran tersebut
    
    actual_self_cure = 0 jika:
      - Tidak bayar, ATAU
      - Bayar tapi melalui collector (SELF_CURE_FLAG = False)
    """
    pay_window = filter_payment_in_window(df_payment, scoring_date, n_days)
    
    self_cure_contracts = (
        pay_window[pay_window['SELF_CURE_FLAG'] == True]['CONTRACT_NO'].unique()
    )
    
    df_features['actual_self_cure'] = (
        df_features['CONTRACT_NO'].isin(self_cure_contracts).astype(int)
    )
    return df_features
```

**Training:**
```python
# Gunakan SELF_CURE_FEATURE_COLS dari settings (subset 12 features)
# Nasabah yang self-cure lebih dipengaruhi karakter mereka sendiri
# (days_to_maturity, payment_rate, self_cure_rate historis)
# bukan oleh seberapa keras kita menagih

model, meta = strategy_recency_weighted(
    df_labeled,
    feature_cols=SELF_CURE_FEATURE_COLS,
    target_col='actual_self_cure',
    decay_rate=0.70
)

# Simpan
joblib.dump({
    'model'        : model,
    'feature_cols' : SELF_CURE_FEATURE_COLS,
    'model_type'   : 'self_cure',
    'trained_at'   : datetime.now().isoformat(),
    **meta
}, SELF_CURE_MODEL_PATH)
```

**Acceptance Criteria:**
- [ ] `SELF_CURE_PROBABILITY` output dalam range [0.0, 1.0]
- [ ] Model hanya menggunakan `SELF_CURE_FEATURE_COLS` (bukan semua 36 features)
- [ ] CV AUC ≥ 0.65 (threshold lebih rendah karena target lebih spesifik dan jarang)
- [ ] Registrasi ke model registry dengan `model_type = 'self_cure'`

---

### TASK-39: Build Roll Forward Sub-Model
**Status**: [ ] Pending
**Dependencies**: TASK-33
**Output file**: `models/roll_forward_model.pkl`

**Instruksi untuk agent:**
Bangun sub-model yang memprediksi apakah cycle nasabah akan **memburuk** bulan berikutnya.

**Mendefinisikan training label:**
```python
def build_roll_forward_label(df_contract_history):
    """
    Butuh data snapshot dua periode berturut-turut.
    
    Target: actual_roll_forward = 1 jika:
      - Bulan depan CYCLE_AKHIR > bulan ini CYCLE_AKHIR
      (contoh: C1 bulan ini → C2 bulan depan = roll forward)
    
    actual_roll_forward = 0 jika:
      - Cycle tetap atau membaik
    
    Cara mendapatkan label:
      - Join snapshot bulan ini dengan snapshot bulan berikutnya
        ON CONTRACT_NO WHERE snapshot_date = bulan_ini + 1 bulan
    """
    current  = df_contract_history[df_contract_history['period'] == 'current']
    next_month = df_contract_history[df_contract_history['period'] == 'next']
    
    joined = current.merge(
        next_month[['CONTRACT_NO', 'cycle_encoded']].rename(
            columns={'cycle_encoded': 'next_cycle_encoded'}
        ),
        on='CONTRACT_NO', how='left'
    )
    
    joined['actual_roll_forward'] = (
        (joined['next_cycle_encoded'] > joined['cycle_encoded'])
        .astype(int)
    )
    return joined
```

**Catatan penting:** Roll forward label membutuhkan **historical snapshots** (bukan hanya snapshot terbaru). Pastikan data historis tersimpan. Jika tidak ada historical snapshot, gunakan `PREV_CYCLE` sebagai proxy:
```python
# Proxy jika tidak ada historical snapshot:
# "Apakah bulan lalu sudah roll forward?" sebagai training signal
df_features['was_rolled_fwd'] = (
    df_features['cycle_encoded'] > df_features['prev_cycle_encoded']
).astype(int)
```

**Acceptance Criteria:**
- [ ] `ROLL_FORWARD_RISK` output dalam range [0.0, 1.0]
- [ ] `cycle_direction` dan `prev_cycle_encoded` adalah fitur terpenting (check feature importance)
- [ ] CV AUC ≥ 0.68
- [ ] Model di-register ke registry dengan `model_type = 'roll_forward'`

---

### TASK-40: Build PTP Success Sub-Model
**Status**: [ ] Pending
**Dependencies**: TASK-34
**Output file**: `models/ptp_success_model.pkl`

**Instruksi untuk agent:**
Bangun sub-model yang memprediksi apakah PTP yang baru dibuat akan ditepati.

**Keunikan model ini: label TIDAK butuh 30 hari tunggu.**
`PTP_STATUS` diupdate oleh collector saat nasabah bayar (KEPT) atau
saat PROMISE_DATE terlewat tanpa pembayaran (BROKEN). Label tersedia lebih cepat.

```python
def build_ptp_label(df_lkp):
    """
    Target: actual_ptp_kept = 1 jika PTP_STATUS = 'KEPT'
            actual_ptp_kept = 0 jika PTP_STATUS = 'BROKEN'
            Exclude: PTP_STATUS = 'OPEN' (belum bisa dilabeli)
    """
    ptp_rows = df_lkp[
        (df_lkp['RESULT_CODE'] == 'PTP') &
        (df_lkp['PTP_STATUS'].isin(['KEPT', 'BROKEN']))
    ].copy()
    
    ptp_rows['actual_ptp_kept'] = (ptp_rows['PTP_STATUS'] == 'KEPT').astype(int)
    return ptp_rows
```

**Note:** Dataset untuk model ini berbeda — bukan per kontrak, tapi **per PTP event**.
Setiap baris adalah satu PTP yang dibuat, dengan label apakah ditepati atau tidak.

**Acceptance Criteria:**
- [ ] Dataset training adalah per-PTP-event (bukan per kontrak)
- [ ] `PTP_SUCCESS_PROBABILITY` dalam range [0.0, 1.0]
- [ ] Fitur `ptp_coverage_ratio` (PTP_AMOUNT/AMBC) ada di antara top features
- [ ] CV AUC ≥ 0.65

---

## PHASE 11 — Scoring Engine & Rules Upgrade

---

### TASK-41: Update Scoring Engine — 4 Model Output
**Status**: [ ] Pending
**Dependencies**: TASK-37, TASK-38, TASK-39, TASK-40, TASK-16
**Output file**: `src/scoring_engine.py` (update)

**Instruksi untuk agent:**
Update `score_contracts()` untuk menjalankan semua 4 model secara paralel.

```python
def score_contracts_multi(df_features_enriched):
    """
    Jalankan semua 4 model dan gabungkan hasilnya.
    Output DataFrame memiliki 4 kolom score baru.
    """
    from config.settings import (
        CHAMPION_MODEL_PATH, SELF_CURE_MODEL_PATH,
        ROLL_FORWARD_MODEL_PATH, PTP_SUCCESS_MODEL_PATH,
        FEATURE_COLS, SELF_CURE_FEATURE_COLS,
        ROLL_FORWARD_FEATURE_COLS, PTP_SUCCESS_FEATURE_COLS
    )

    models = {
        'RECOVERY_SCORE'         : (CHAMPION_MODEL_PATH,    FEATURE_COLS),
        'SELF_CURE_PROBABILITY'  : (SELF_CURE_MODEL_PATH,   SELF_CURE_FEATURE_COLS),
        'ROLL_FORWARD_RISK'      : (ROLL_FORWARD_MODEL_PATH, ROLL_FORWARD_FEATURE_COLS),
        'PTP_SUCCESS_PROBABILITY': (PTP_SUCCESS_MODEL_PATH,  PTP_SUCCESS_FEATURE_COLS),
    }

    df = df_features_enriched.copy()

    for output_col, (model_path, feature_cols) in models.items():
        if not os.path.exists(model_path):
            print(f"  ⚠️  {output_col}: model not found at {model_path}, skipping")
            df[output_col] = None
            continue

        artifact = joblib.load(model_path)
        model    = artifact['model']
        X        = df[feature_cols]

        df[output_col] = model.predict_proba(X)[:, 1].round(4)
        print(f"  ✓ {output_col}: scored {len(df):,} contracts")

    return df
```

**Acceptance Criteria:**
- [ ] Fungsi menghasilkan 4 kolom score baru
- [ ] Jika salah satu model tidak ditemukan → output NULL untuk kolom itu, tidak error
- [ ] Semua score dalam range [0.0, 1.0]
- [ ] Timing: 4 model berjalan < 60 detik untuk 10.000 kontrak

---

### TASK-42: Update Business Rules
**Status**: [ ] Pending
**Dependencies**: TASK-41, TASK-18
**Output file**: `src/business_rules.py` (update)

**Instruksi untuk agent:**
Update 3 business rules yang berubah karena score baru.

**1. Update `apply_risk_segment()` — gunakan SELF_CURE_PROBABILITY:**
```python
# SEBELUM: Self-cure hanya dari RECOVERY_SCORE + DPD + payment_rate
# SESUDAH: Jika SELF_CURE_PROBABILITY tersedia, gunakan sebagai input utama

cond_self_cure = (
    (df['RECOVERY_SCORE'] >= 0.70) &
    (df['DPD_CURRENT'] <= 7) &
    (df['payment_rate'].fillna(0) >= 0.80) &
    (df['SELF_CURE_PROBABILITY'].fillna(0) >= SELF_CURE_PROB_THRESHOLD)
)
# Self-cure threshold dari settings: 0.70
# Lebih ketat: hanya Self-cure jika KEDUA kondisi terpenuhi
```

**2. Update `apply_priority()` — incorporate ROLL_FORWARD_RISK:**
```python
def get_priority_row(row):
    base_priority = get_matrix_priority(row['RISK_SEGMENT'], row['total_ots'])

    # Eskalasi priority jika roll forward risk tinggi
    if row.get('ROLL_FORWARD_RISK', 0) >= ROLL_FORWARD_HIGH_RISK:
        # Naikkan satu level
        escalation_map = {
            'Low'     : 'Medium',
            'Medium'  : 'High',
            'High'    : 'Critical',
            'Critical': 'Critical',  # sudah paling tinggi
        }
        return escalation_map.get(base_priority, base_priority)

    return base_priority
```

**3. Update `apply_nba()` — gunakan RPC_FLAG dan SELF_CURE_PROBABILITY:**
```python
def get_nba_row(row):
    # ... logika lama tetap ada ...

    # Override baru 1: nasabah self-cure tinggi → WA saja, jangan visit
    if row.get('SELF_CURE_PROBABILITY', 0) >= SELF_CURE_PROB_THRESHOLD:
        return 'WA'  # tidak perlu collector aktif

    # Override baru 2: RPC rate sangat rendah → Visit untuk verify alamat
    if row.get('rpc_rate', 1) < RPC_RATE_LOW_THRESHOLD:
        return max_channel(current_nba, 'Visit')  # minimal Visit

    # Override baru 3: near-maturity + saldo kecil → WA cukup
    if (row.get('days_to_maturity', 999) < DAYS_TO_MATURITY_SHORT and
        row.get('ambc', 999_999) < row.get('INSTALLMENT_AMOUNT', 0) * 2):
        return 'WA'

    return nba  # NBA default dari logika lama
```

**Acceptance Criteria:**
- [ ] Self-cure segment sekarang membutuhkan `SELF_CURE_PROBABILITY >= 0.70`
- [ ] Priority naik satu level jika `ROLL_FORWARD_RISK >= 0.75`
- [ ] Nasabah dengan `SELF_CURE_PROBABILITY >= 0.70` → NBA = WA (override semua)
- [ ] Nasabah dengan `rpc_rate < 0.30` → minimum NBA = Visit
- [ ] Backward compatible jika kolom baru NULL (gunakan default behavior lama)

---

### TASK-43: Update QC Checks
**Status**: [ ] Pending
**Dependencies**: TASK-42, TASK-19
**Output file**: `src/scoring_engine.py` (update `run_quality_check`)

**Instruksi untuk agent:**
Tambahkan validasi baru untuk 3 kolom output baru.

```python
# Tambahkan ke run_quality_check():

# Range check untuk score baru
for col in ['SELF_CURE_PROBABILITY', 'ROLL_FORWARD_RISK', 'PTP_SUCCESS_PROBABILITY']:
    if col in df_output.columns and df_output[col].notna().any():
        if not df_output[col].dropna().between(0, 1).all():
            errors.append(f"{col} ada yang di luar range 0–1")

# Konsistensi check: Self-cure harus punya SELF_CURE_PROBABILITY tinggi
selfcure_rows = df_output[df_output['RISK_SEGMENT'] == 'Self-cure']
if len(selfcure_rows) > 0 and 'SELF_CURE_PROBABILITY' in df_output.columns:
    avg_sc_prob = selfcure_rows['SELF_CURE_PROBABILITY'].mean()
    if avg_sc_prob < 0.50:
        warnings.append(
            f"Self-cure segment avg SELF_CURE_PROBABILITY={avg_sc_prob:.2f} < 0.50 "
            "— mungkin ada inkonsistensi antara rules dan sub-model"
        )

# Roll forward: Won't Pay harus punya ROLL_FORWARD_RISK rata-rata lebih tinggi dari Self-cure
wont_pay_rfr = df_output[df_output['RISK_SEGMENT']=="Won't Pay"]['ROLL_FORWARD_RISK'].mean()
self_cure_rfr = df_output[df_output['RISK_SEGMENT']=='Self-cure']['ROLL_FORWARD_RISK'].mean()
if wont_pay_rfr < self_cure_rfr:
    warnings.append("Won't Pay ROLL_FORWARD_RISK lebih rendah dari Self-cure — aneh")
```

**Acceptance Criteria:**
- [ ] QC gagal (raise ValueError) jika score baru di luar range [0,1]
- [ ] QC warning jika Self-cure segment memiliki avg SELF_CURE_PROBABILITY < 0.50
- [ ] QC hanya warning (bukan error) untuk inkonsistensi antar-model (karena model terpisah)

---

### TASK-44: Update Daily Runner
**Status**: [ ] Pending
**Dependencies**: TASK-41, TASK-42, TASK-43, TASK-20
**Output file**: `pipelines/daily_scoring.py` (update)

**Instruksi untuk agent:**
Update `run_daily_scoring()` untuk menggunakan `score_contracts_multi()`.

Perubahan minimal yang diperlukan:
1. Ganti `score_contracts()` → `score_contracts_multi()`
2. Tambahkan `compute_confidence_level()` tetap berjalan (hanya untuk RECOVERY_SCORE)
3. Summary output sekarang mencakup distribusi semua 4 scores
4. UPSERT sekarang mencakup 3 kolom output baru

```python
# Tambahkan ke summary print:
print(f"\n  MULTI-SCORE SUMMARY:")
print(f"  Avg RECOVERY_SCORE       : {scored['RECOVERY_SCORE'].mean():.4f}")
print(f"  Avg SELF_CURE_PROB       : {scored['SELF_CURE_PROBABILITY'].mean():.4f}")
print(f"  Avg ROLL_FORWARD_RISK    : {scored['ROLL_FORWARD_RISK'].mean():.4f}")
print(f"  Avg PTP_SUCCESS_PROB     : {scored['PTP_SUCCESS_PROBABILITY'].mean():.4f}")
print(f"  Will Self-Cure (prob>0.7): {(scored['SELF_CURE_PROBABILITY']>=0.70).sum():,}")
print(f"  High Roll Forward Risk   : {(scored['ROLL_FORWARD_RISK']>=0.75).sum():,}")
```

**Acceptance Criteria:**
- [ ] Daily runner menghasilkan 9 kolom output (6 lama + 3 baru)
- [ ] Semua 4 model di-score dalam satu daily run
- [ ] Jika sub-model belum ada (belum ditraining) → kolom = NULL, daily run tidak gagal

---

## PHASE 12 — MLOps & Test Upgrade

---

### TASK-45: Update MLOps Outcome Labeler untuk Sub-Models
**Status**: [ ] Pending
**Dependencies**: TASK-22, TASK-38, TASK-39, TASK-40
**Output file**: `src/outcome_labeler.py` (update)

**Instruksi untuk agent:**
Update `label_historical_scores()` untuk juga mengisi 3 kolom label baru
di tabel `scoring_labels`:

```python
# Tambahkan ke label_historical_scores():

# 1. actual_self_cure: bayar dalam window DAN SELF_CURE_FLAG = True
pay_self_cure = pay_window[
    (pay_window['PAY_STATUS'].isin(['Full', 'Partial'])) &
    (pay_window['SELF_CURE_FLAG'] == True)
]
self_cure_contracts = set(pay_self_cure['CONTRACT_NO'].unique())
labeled['actual_self_cure'] = (
    labeled['CONTRACT_NO'].isin(self_cure_contracts).astype(int)
)

# 2. actual_roll_forward: butuh next period snapshot
# Gunakan kolom PREV_CYCLE dari snapshot periode berikutnya
# (contract_no pada bulan scoring → PREV_CYCLE bulan berikutnya = CYCLE_AKHIR bulan ini)
# Jika tidak ada data → NULL

# 3. actual_ptp_kept: dari PTP_STATUS pada LKP records yang terkait
# Label ini TIDAK membutuhkan 30 hari tunggu
ptp_kept_contracts = set(
    df_lkp[
        (df_lkp['RESULT_CODE'] == 'PTP') &
        (df_lkp['PTP_STATUS'] == 'KEPT')
    ]['CONTRACT_NO'].unique()
)
labeled['actual_ptp_kept'] = (
    labeled['CONTRACT_NO'].isin(ptp_kept_contracts).astype(int)
)
```

**Acceptance Criteria:**
- [ ] `scoring_labels` tabel memiliki 3 kolom label baru terisi
- [ ] `actual_ptp_kept` terisi tanpa perlu tunggu 30 hari
- [ ] `actual_self_cure` NULL untuk kontrak tanpa data SELF_CURE_FLAG

---

### TASK-46: Update dan Tambah Test Cases
**Status**: [ ] Pending
**Dependencies**: TASK-33–TASK-45
**Output file**: `tests/` (update file-file yang sudah ada + tambah baru)

**Instruksi untuk agent:**
Update semua file test yang ada dan tambahkan test untuk fitur/model baru.

**`tests/test_features.py` — tambah test:**
```python
# Tests baru
def test_cycle_direction_worsening():     # C1→C2 → direction = +1
def test_cycle_direction_improving():     # C2→C1 → direction = -1
def test_days_to_maturity_positive():     # future date → positive value
def test_days_to_maturity_past():         # past date → clipped to 0
def test_rpc_rate_calculation():          # 3 dari 5 RPC True → 0.6
def test_ptp_status_direct():             # PTP_STATUS='BROKEN' → tidak pakai window
def test_self_cure_rate():                # 2 dari 3 payment SELF_CURE=True → 0.667
def test_recovery_ratio():                # loan=100jt, ots=30jt → ratio=0.7
```

**`tests/test_rules.py` — tambah test:**
```python
def test_self_cure_needs_high_prob():     # prob=0.50 (bawah threshold) → bukan Self-cure
def test_priority_escalation_roll_fwd(): # Medium + roll_fwd=0.80 → naik jadi High
def test_nba_selfcure_override():         # self_cure_prob=0.80 → NBA=WA (override apapun)
def test_nba_low_rpc_visit():             # rpc_rate=0.10 → minimal Visit
def test_nba_near_maturity():             # days_to_maturity=20, ambc kecil → WA
```

**`tests/test_scoring.py` — tambah test:**
```python
def test_multi_model_output_columns():   # output punya 4 kolom score
def test_missing_submodel_graceful():    # sub-model tidak ada → NULL, tidak error
```

**Acceptance Criteria:**
- [ ] `pytest tests/` → semua test PASS (termasuk lama + baru)
- [ ] Tidak ada test yang break karena perubahan dari TASK-33–TASK-45

---

### TASK-47: Buat Script Migrasi Data Historis
**Status**: [ ] Pending
**Dependencies**: TASK-31
**Output file**: `config/migrate_historical_data.py`

**Instruksi untuk agent:**
Buat script yang mengisi nilai default untuk kolom baru pada data historis
yang belum memiliki field tersebut.

```python
# migrate_historical_data.py
# Dijalankan SEKALI setelah schema upgrade untuk mengisi data historis

def migrate_historical_defaults(engine):
    """
    Isi nilai default yang masuk akal untuk data historis
    yang belum punya kolom baru.
    """
    with engine.connect() as conn:

        # Contract Snapshot: AMBC = total_ots jika NULL
        conn.execute("""
            UPDATE contract_snapshot
            SET ambc = prnc_ots + intr_ots
            WHERE ambc IS NULL
        """)

        # Contract Snapshot: PREV_CYCLE = CYCLE_AKHIR jika NULL
        # (asumsi stabil, tidak ada perubahan)
        conn.execute("""
            UPDATE contract_snapshot
            SET prev_cycle = cycle_akhir
            WHERE prev_cycle IS NULL
        """)

        # LKP Interaction: CONTACT_SUCCESS_FLAG = True jika ada RESULT_CODE
        # (jika ada hasil interaksi, berarti kontak berhasil)
        conn.execute("""
            UPDATE lkp_interaction
            SET contact_success_flag = TRUE
            WHERE contact_success_flag IS NULL
            AND result_code IS NOT NULL
        """)

        # LKP Interaction: PTP_STATUS inference untuk data lama
        # BROKEN jika PTP tapi tidak ada pembayaran dalam 7 hari
        # KEPT jika PTP dan ada pembayaran dalam 7 hari
        # (inference tetap dipakai untuk data historis yang belum punya field ini)
        conn.execute("""
            UPDATE lkp_interaction li
            SET ptp_status = CASE
                WHEN EXISTS (
                    SELECT 1 FROM payment_history ph
                    WHERE ph.contract_no = li.contract_no
                    AND ph.actual_pay_date BETWEEN li.promise_date
                                               AND li.promise_date + INTERVAL '7 days'
                    AND ph.pay_status IN ('Full', 'Partial')
                ) THEN 'KEPT'
                WHEN li.promise_date < CURRENT_DATE THEN 'BROKEN'
                ELSE 'OPEN'
            END
            WHERE li.result_code = 'PTP'
            AND li.ptp_status IS NULL
        """)

        # Payment History: SELF_CURE_FLAG = TRUE jika tidak ada LKP
        # dalam 7 hari sebelum pembayaran (inference untuk data historis)
        conn.execute("""
            UPDATE payment_history ph
            SET self_cure_flag = NOT EXISTS (
                SELECT 1 FROM lkp_interaction li
                WHERE li.contract_no = ph.contract_no
                AND li.action_date BETWEEN ph.actual_pay_date - INTERVAL '7 days'
                                       AND ph.actual_pay_date
            )
            WHERE self_cure_flag IS NULL
        """)

        print("Migration complete.")
        conn.commit()
```

**Acceptance Criteria:**
- [ ] Script berjalan tanpa error pada database yang sudah berisi data
- [ ] Setelah migration: tidak ada NULL pada kolom-kolom yang sudah dapat default
- [ ] `PTP_STATUS` terisi (KEPT/BROKEN/OPEN) untuk semua LKP dengan RESULT_CODE='PTP'
- [ ] Script idempotent: aman dijalankan dua kali (tidak double-update)

---

## RINGKASAN UPGRADE

```
PHASE 8  │ Schema & Config (T31–T32) │ 2 tasks  │ Fondasi perubahan
PHASE 9  │ Feature Engineering       │ 4 tasks  │ 36 features (dari 21)
          │ Upgrade (T33–T36)        │          │ 3 inference → direct data
PHASE 10 │ Sub-Model Training        │ 4 tasks  │ 4 model (dari 1)
          │ (T37–T40)                │          │
PHASE 11 │ Scoring & Rules Upgrade   │ 4 tasks  │ 4 score output, rules baru
          │ (T41–T44)                │          │
PHASE 12 │ MLOps & Test Upgrade      │ 3 tasks  │ Label 3 sub-model,
          │ (T45–T47)                │          │ test update, migrasi data

TOTAL TASK TAMBAHAN : 17 tasks (TASK-31 s/d TASK-47)
TOTAL KESELURUHAN   : 47 tasks (TASK-01 s/d TASK-47)

Dependency kritis setelah upgrade:
  TASK-37 (retrain main model) HARUS pakai FEATURE_COLS baru dari TASK-32
  TASK-38/39/40 (sub-models) bisa dikerjakan PARALEL satu sama lain
  TASK-41 (multi-model scorer) HARUS menunggu minimal TASK-37 selesai
  TASK-47 (migrasi data) HARUS dijalankan SEBELUM TASK-37/38/39/40
           karena model butuh data historis yang sudah termigasi
```