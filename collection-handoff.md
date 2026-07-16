# CollectAI — Project Handoff Document
## Konteks Lengkap untuk Melanjutkan di Sesi Baru

> Dokumen ini adalah ringkasan lengkap semua keputusan, arsitektur, dan status
> proyek CollectAI. Upload dokumen ini bersama file-file pendukung lainnya
> ke sesi Claude baru agar konteks terjaga sepenuhnya.

---

## 1. IDENTITAS PROYEK

**Nama sistem**: CollectAI
**Tujuan**: Sistem AI untuk debt collection — memprioritaskan nasabah, merekomendasikan
tindakan penagihan (NBA), dan memperbarui profil perilaku nasabah secara otomatis.

**Stack keputusan**:
- Model ML: XGBoost / LightGBM (Gradient Boosting)
- Bahasa: Python
- Database: PostgreSQL (schema SQL sudah dibuat)
- Scheduler: Cron / Apache Airflow
- Model versioning: JSON-based registry + joblib artifacts

---

## 2. STRUKTUR DATA

### 2.1 Input Tables (4 tabel sumber)

```
customer_master
  CUST_ID (PK), CUST_AGE, CUST_INCOME_LEVEL (Low/Mid/High),
  CUST_OCCUPATION, CUST_SEGMENT, CUST_REGION

contract_snapshot                             ← snapshot harian
  CONTRACT_NO (PK), CUST_ID (FK),
  DPD_CURRENT, PRNC_OTS, INTR_OTS, CYCLE_AKHIR (C0/C1/C2/C3),
  PRODUCT_TYPE,
  [BARU] AMBC, PREV_CYCLE, LOAN_AMOUNT, INSTALLMENT_AMOUNT,
         MATURITY_DATE, OVERDUE_INSTALLMENT_COUNT, LATE_FEE_AMOUNT

payment_history
  PAYMENT_ID (PK), CONTRACT_NO (FK),
  DUE_DATE, ACTUAL_PAY_DATE, PAYMENT_AMOUNT, PAY_STATUS, DELAY_DAYS,
  [BARU] SELF_CURE_FLAG (bool), RECOVERY_SOURCE (WA/SMS/Deskcoll/Visit/Somasi)

lkp_interaction                               ← log aksi penagihan
  LKP_ID (PK), CONTRACT_NO (FK),
  ACTION_DATE, TREATMENT_TYPE, RESULT_CODE, PROMISE_DATE,
  COLLECTOR_ID, INTERACTION_SCORE (1–5),
  [BARU] PTP_AMOUNT, PTP_STATUS (OPEN/KEPT/BROKEN),
         RPC_FLAG (bool), CONTACT_SUCCESS_FLAG (bool)
```

### 2.2 Output Tables (2 tabel hasil)

```
ai_intelligence_output                        ← per CONTRACT_NO, refresh harian
  CONTRACT_NO (PK), CUST_ID,
  RECOVERY_SCORE (0.00–1.00),
  CONFIDENCE_LEVEL (0.00–1.00),
  CONFIDENCE_CATEGORY (HIGH/MEDIUM/LOW),
  RISK_SEGMENT (Self-cure/Can Pay/Cannot Pay/Won't Pay),
  NBA_RECOMMENDATION (WA/Deskcoll/Visit/Somasi/Pickup),
  PRIORITY_LEVEL (Critical/High/Medium/Low),
  SCORING_DATE,
  [BARU] SELF_CURE_PROBABILITY (0.00–1.00),
  [BARU] ROLL_FORWARD_RISK (0.00–1.00),
  [BARU] PTP_SUCCESS_PROBABILITY (0.00–1.00)

customer_behavioral_standing (CBS)            ← per CUST_ID, refresh mingguan
  CUST_ID (PK),
  ACTIVE_CONTRACT_COUNT,           ← jumlah kontrak aktif nasabah ini
  TOTAL_ACTIVE_OTS,                ← SUM OTS semua kontrak aktif
  BEHAVIORAL_GRADE (A/B/C/D),
  RECOVERY_EFFORT_LEVEL (Low/Mid/High),
  PTP_RELIABILITY_INDEX (0.0–1.0 atau NULL),
  COLLECTION_SENSITIVITY (channel paling efektif),
  B_LIST_STATUS (Y/N),
  UPDATE_TIMESTAMP
```

---

## 3. KEPUTUSAN ARSITEKTUR YANG SUDAH DIBUAT

### 3.1 CBS adalah per CUST_ID, bukan per CONTRACT
**Keputusan**: CBS merepresentasikan satu nasabah secara keseluruhan,
mengagregasi semua kontrak aktif dan historis.

**Alasan**: Satu nasabah bisa punya banyak kontrak. Jika CBS per kontrak,
kita kehilangan gambaran utuh. TOTAL_ACTIVE_OTS terutama penting —
nasabah dengan 3 kontrak aktif beban totalnya sangat berbeda dari yang 1 kontrak.

**CBS feeds into AI output**: CBS bukan berdiri sendiri — dia menjadi enrichment
input ke model scoring per kontrak.

### 3.2 Recovery Score adalah probabilitas (bukan label)
**Keputusan**: Output model adalah float 0.00–1.00, bukan YES/NO.

**Alasan**: Collector butuh ranking, bukan label. Score 0.92 vs 0.54 keduanya
"akan bayar" tapi butuh treatment sangat berbeda.

### 3.3 CONFIDENCE_LEVEL bukan output model ML
**Keputusan**: CONFIDENCE_LEVEL dihitung terpisah dari 3 komponen:
- A (40%): Data Completeness — % fitur kunci yang tidak NULL
- B (35%): History Depth — kedalaman payment + LKP history
- C (25%): Model Certainty — jarak RECOVERY_SCORE dari 0.5

**Alasan**: Model confidence ≠ data quality. Nasabah dengan score 0.95
bisa tetap LOW confidence jika datanya minim (nasabah baru).

### 3.4 Tiga inference digantikan data langsung
**Keputusan setelah analisis data tambahan**:

| Yang Lama (Inference) | Yang Baru (Direct) |
|---|---|
| `ptp_fulfillment_rate` dari payment window 7 hari | Langsung dari `PTP_STATUS = KEPT/BROKEN` |
| `channel_effectiveness` dari proximity LKP→Payment | Langsung dari `RECOVERY_SOURCE` |
| `broken_ptp_count` dari subtraksi dua angka perkiraan | Langsung dari `COUNT(PTP_STATUS='BROKEN')` |

### 3.5 Arsitektur 4 model terpisah
**Keputusan**: Dari 1 model menjadi 4 model, masing-masing menjawab pertanyaan berbeda:

```
Model 1: Recovery Scoring    → RECOVERY_SCORE
         "Apakah nasabah akan bayar dalam 30 hari?"
         Target: actual_paid_within_30d
         Features: 36 features (semua)

Model 2: Self-cure           → SELF_CURE_PROBABILITY
         "Apakah mereka akan bayar TANPA kita hubungi?"
         Target: actual_self_cure (SELF_CURE_FLAG=True AND paid)
         Features: 12 features (karakter nasabah, bukan effort collector)

Model 3: Roll Forward        → ROLL_FORWARD_RISK
         "Apakah cycle akan memburuk bulan depan?"
         Target: actual_roll_forward (next_cycle > current_cycle)
         Features: 14 features (posisi dan arah current cycle)

Model 4: PTP Success         → PTP_SUCCESS_PROBABILITY
         "Apakah PTP yang baru dibuat akan ditepati?"
         Target: actual_ptp_kept (PTP_STATUS = KEPT)
         Features: 11 features (behavior LKP dan PTP history)
         NOTE: Label tersedia real-time, tidak perlu tunggu 30 hari
```

### 3.6 MLOps: Model belajar sendiri via feedback loop
**Keputusan**: Sistem memiliki closed-loop learning:
- Setiap score yang dihasilkan hari ini → 30 hari kemudian dilabeli dari Payment History
- Dataset training tumbuh otomatis setiap minggu
- Model di-monitor AUC + PSI (Population Stability Index) setiap minggu
- Retrain dipicu otomatis jika AUC < 0.68 atau ada PSI critical
- **Recency-weighted strategy**: semua data dipakai, tapi data baru diberi bobot lebih tinggi (decay 0.7/bulan)

### 3.7 Champion-Challenger
**Keputusan**: Model baru tidak langsung menggantikan model lama.
- Model baru (Challenger) berjalan shadow mode 7–14 hari
- Kedua model score kontrak yang sama, tapi hanya Champion yang dipakai operasional
- Challenger dipromote hanya jika AUC-nya lebih baik ≥ 0.02 poin
- Champion lama selalu diarsipkan (rollback tersedia)

---

## 4. FEATURE ENGINEERING LENGKAP

### 4.1 Contract-Level Features (22 features)

```python
# LAMA (13 features — masih ada):
dpd_current, cycle_encoded (C0=0,C1=1,C2=2,C3+=3), total_ots (PRNC+INTR),
payment_rate, partial_rate, avg_delay_days, days_since_last_pay,
ptp_fulfillment_rate*, avg_interaction_score, last_result_code_encoded
(Bayar=4,PTP=3,RK=2,TBD=1,Menolak=0), treatment_count, rejection_count,
payment_count

# BARU (9 features — tambahan data upgrade):
ambc,                            # AMBC langsung dari data
ambc_to_ots_ratio,               # AMBC / total_ots (clip 0–1)
prev_cycle_encoded,              # encode PREV_CYCLE sama seperti cycle
cycle_direction,                 # cycle_encoded - prev_cycle_encoded
days_to_maturity,                # (MATURITY_DATE - TODAY).days (clip min 0)
recovery_ratio,                  # (LOAN_AMOUNT - total_ots) / LOAN_AMOUNT
installment_to_income_ratio,     # INSTALLMENT_AMOUNT / income_proxy
overdue_installment_count,       # langsung dari data
late_fee_amount                  # langsung dari data
```

### 4.2 LKP-Level Features (6 features, gabung ke contract)

```python
# LAMA (2 features):
avg_interaction_score, rejection_count  ← sudah masuk contract features

# BARU (4 features):
rpc_rate,                        # COUNT(RPC_FLAG=True) / COUNT(all contacts)
contact_success_rate,            # COUNT(CONTACT_SUCCESS=True) / COUNT(all)
ptp_coverage_ratio,              # SUM(PTP_AMOUNT) / AMBC (clip 0–2)
open_ptp_count                   # COUNT(PTP_STATUS='OPEN')
```

### 4.3 Payment-Level Features (2 features baru)

```python
self_cure_rate,                  # COUNT(SELF_CURE_FLAG=True) / COUNT(payments)
recovery_source_encoded          # MODE(RECOVERY_SOURCE) encoded (WA=1,...,Somasi=5)
```

### 4.4 Customer-Level Features dari CBS (8 features, enrichment)

```python
ptp_reliability_index,           # langsung dari PTP_STATUS=KEPT/BROKEN (bukan infer)
delay_trend,                     # slope DELAY_DAYS vs time (6 bulan)
historical_default_count,        # COUNT kontrak yang pernah C3+
income_debt_ratio,               # total_active_ots / income_proxy
active_contract_count,
total_active_ots,
behavioral_grade_encoded,        # A=3, B=2, C=1, D=0
b_list_flag                      # Y=1, N=0
```

**Total FEATURE_COLS (main model): 36 features**

---

## 5. BUSINESS RULES LENGKAP

### 5.1 RISK_SEGMENT (top-down, first-match)

```
1. Won't Pay  → RECOVERY_SCORE < 0.30
               AND (rejection_count >= 2 OR last_result_code_encoded <= 1)

2. Cannot Pay → RECOVERY_SCORE >= 0.30 AND < 0.50
               AND (broken_ptp_count > 0 OR income_debt_ratio > 2.0)

3. Self-cure  → RECOVERY_SCORE >= 0.70
               AND dpd_current <= 7
               AND payment_rate >= 0.80
               AND SELF_CURE_PROBABILITY >= 0.70    ← baru setelah upgrade

4. Can Pay    → semua kondisi lain
```

### 5.2 NBA_RECOMMENDATION

```
Self-cure                    → WA
Self-cure prob >= 0.70       → WA (override semua) ← baru
Can Pay + cycle C0/C1        → WA
Can Pay + cycle C2/C3        → Deskcoll
Cannot Pay + cycle C0/C1     → Deskcoll
Cannot Pay + cycle C2/C3     → Visit
Won't Pay + OTS < 5jt        → Visit
Won't Pay + OTS 5-20jt       → Somasi
Won't Pay + OTS > 20jt + default >= 2 → Pickup

Override dari CBS:
  Jika COLLECTION_SENSITIVITY > rank NBA default → gunakan CBS channel
  Channel rank: WA=1, Deskcoll=2, Visit=3, Somasi=4, Pickup=5
  Override hanya boleh NAIK, tidak boleh turun

Override baru setelah upgrade:
  rpc_rate < 0.30 → minimum Visit (perlu establish direct contact)
  days_to_maturity < 60 AND ambc < 2×installment → WA (near-maturity kecil)
```

### 5.3 PRIORITY_LEVEL (matrix RISK_SEGMENT × OTS tier)

```
OTS Tier: Rendah < 5jt | Menengah 5–20jt | Tinggi > 20jt

             Rendah    Menengah  Tinggi
Won't Pay  : High      Critical  Critical
Cannot Pay : Medium    High      Critical
Can Pay    : Low       Medium    High
Self-cure  : Low       Low       Medium

Eskalasi setelah upgrade:
  Jika ROLL_FORWARD_RISK >= 0.75 → naikkan priority satu level
  (Low→Medium, Medium→High, High→Critical, Critical tetap Critical)
```

### 5.4 BEHAVIORAL_GRADE

```
Composite behavioral score:
  = (payment_rate_weighted × 0.30)
  + (ptp_reliability_index × 0.25)
  + (interaction_score_norm × 0.20)    ← (avg_score - 1) / 4
  + (delay_score × 0.25)               ← max(0, 1 - avg_delay/90)

Grade A: score >= 0.80
Grade B: score >= 0.60
Grade C: score >= 0.40
Grade D: score < 0.40

Override paksa ke Grade D jika:
  broken_ptp_count >= 5  ATAU
  historical_default_count >= 3  ATAU
  ptp_reliability_index < 0.10 AND total_ptp_made >= 3
```

### 5.5 B_LIST_STATUS = 'Y' jika salah satu:

```
- BEHAVIORAL_GRADE = 'D'
- broken_ptp_count >= 5
- Pernah TREATMENT_TYPE = 'Somasi Hukum' atau 'Pickup'
- historical_default_count >= 3
- ptp_reliability_index < 0.10 AND total_ptp_made >= 3

PENTING: B_LIST 'Y' tidak otomatis kembali ke 'N'.
Reset hanya via manual supervisor dengan flag force_reset=True.
```

---

## 6. DAILY BATCH FLOW

```
Setiap malam (23:00):
  Step 1: Load data terbaru (contract snapshot, payment, LKP)
  Step 2: Compute 22 contract-level features per CONTRACT_NO
  Step 3: Update CBS (customer-level features + business rules) untuk CUST_ID yang berubah
  Step 4: Enrich contract features dengan CBS (36 features total)
  Step 5: Score dengan 4 model paralel
  Step 6: Compute CONFIDENCE_LEVEL (3 komponen weighted)
  Step 7: Apply business rules (RISK_SEGMENT, NBA, PRIORITY)
  Step 8: Quality check (range, distribusi, konsistensi)
  Step 9: UPSERT ke ai_intelligence_output
  Step 10: Log + alert ke supervisor

Triggered refresh (non-batch):
  Pembayaran masuk → re-score CONTRACT_NO tersebut
  Kontrak closed   → update CBS untuk CUST_ID terkait
  Manual override B_LIST → update CBS langsung

Setiap minggu (Senin 06:00):
  Step 1: Label historical scoring outcomes (30+ hari lalu)
  Step 2: Monitor model performance (AUC + calibration)
  Step 3: Drift detection (PSI per feature)
  Step 4: Retrain challenger jika diperlukan
  Step 5: Shadow score jika ada challenger
  Step 6: Evaluate champion vs challenger setelah 7–14 hari shadow
  Step 7: Promote challenger jika AUC delta >= 0.02
```

---

## 7. STATUS TASK LIST

### TASK-01 s/d TASK-30 — SELESAI ✅

Semua task di CollectAI_Agent_Tasks.md sudah dikerjakan.

```
PHASE 1: Infrastructure (T01–T04)       ✅ Selesai
PHASE 2: Feature Engineering (T05–T08)  ✅ Selesai
PHASE 3: CBS Builder (T09–T11)          ✅ Selesai
PHASE 4: Model Training (T12–T15)       ✅ Selesai
PHASE 5: Daily Scoring (T16–T21)        ✅ Selesai
PHASE 6: MLOps (T22–T26)               ✅ Selesai
PHASE 7: Integration & Test (T27–T30)  ✅ Selesai
```

### TASK-31 s/d TASK-47 — PENDING ⏳

Upgrade tasks dari CollectAI_Data_Upgrade_Tasks.md — belum dikerjakan.

```
PHASE 8:  Schema & Config (T31–T32)        ⏳ Pending
PHASE 9:  Feature Engineering Upgrade      ⏳ Pending
          (T33–T36)
PHASE 10: Sub-Model Training (T37–T40)     ⏳ Pending
PHASE 11: Scoring & Rules Upgrade (T41–T44)⏳ Pending
PHASE 12: MLOps & Test Upgrade (T45–T47)   ⏳ Pending

Urutan eksekusi yang harus diikuti:
T47 (migrasi data) → T31 → T32 → T33 → T34 → T35 → T36
→ T37 + T38 + T39 + T40 (paralel) → T41 → T42 → T43 → T44
→ T45 → T46
```

---

## 8. FILE-FILE YANG ADA

Upload semua file ini ke sesi baru bersama dokumen ini:

```
CollectAI_System_Rules.md         ← Skema tabel, formula lengkap, business rules,
                                     daily flow, QC checks, konfigurasi threshold

CollectAI_Scoring_Engine.md       ← Kode Python lengkap: feature engineering,
                                     training model, RECOVERY_SCORE scoring,
                                     CONFIDENCE_LEVEL calculation, business rules

CollectAI_MLOps_Pipeline.md       ← Kode Python lengkap: outcome labeler,
                                     model monitor (PSI), retrain strategies,
                                     champion-challenger, model registry,
                                     weekly orchestrator

CollectAI_Agent_Tasks.md          ← 30 task (T01–T30) yang sudah selesai.
                                     Berisi instruksi detail per task,
                                     acceptance criteria, dan dependency map

CollectAI_Data_Upgrade_Tasks.md   ← 17 task upgrade (T31–T47) yang belum dikerjakan.
                                     Analisis 19 field tambahan (14 diterima, 5 ditolak),
                                     kode upgrade feature engineering,
                                     panduan sub-model training

CollectAI_Workflow.jsx            ← Diagram workflow interaktif (React component)
                                     untuk visualisasi sistem 4-layer
```

---

## 9. KONTEKS DISKUSI PENTING

Beberapa keputusan dibuat karena diskusi mendalam. Poin-poin ini penting
agar tidak diulang dari awal:

**Kenapa CBS harus per CUST_ID, bukan per CONTRACT?**
Awalnya CBS didesain per kontrak (ada field LAST_CONTRACT_NO).
Dikoreksi karena nasabah multi-kontrak kehilangan gambaran utuh.
TOTAL_ACTIVE_OTS adalah field kunci yang tidak bisa ada jika CBS per kontrak.

**Kenapa model feedback loop lebih tahan krisis (COVID-19 scenario)?**
Model statis buta permanen. Feedback loop: PSI detector aktif minggu pertama
saat distribusi fitur bergeser drastis → retrain dalam bulan pertama →
model belajar bahwa "delay tinggi di seluruh portofolio = force majeure, bukan karakter buruk."
Setelah krisis berlalu, model punya memori lintas siklus yang tidak dimiliki model statis.

**Kenapa recency-weighted bukan rolling window?**
Rolling window membuang data historis yang mungkin relevan.
Full retrain tidak sensitif terhadap perubahan terkini.
Recency-weighted: gunakan semua data, tapi bobot 0.7^bulan_lalu —
data 6 bulan lalu hanya berbobot 0.12, hampir tidak berpengaruh,
tapi tetap ada untuk kasus-kasus langka (nasabah multi-default).

**Kenapa shadow scoring butuh CONTRACT_NO dan CUST_ID?**
Shadow scores perlu di-JOIN ke scoring_labels 30 hari kemudian
untuk mengetahui model mana yang lebih akurat.
Tanpa CONTRACT_NO, tidak bisa tahu prediksi mana yang benar.
CUST_ID untuk analisis breakdown per tipe nasabah.

**Kapan challenger dibuat?**
Bukan setiap ada pembayaran. Pembayaran → re-score kontrak itu saja.
Challenger dibuat hanya saat: AUC turun < 0.68 ATAU PSI critical >= 2 fitur.
Selalu hanya satu challenger pada satu waktu.

**Field yang ditolak dari data tambahan (dan alasannya):**
- SNAPSHOT_DATE: infrastructure field, tidak ada signal prediktif
- TENOR_MONTH: redundan, MATURITY_DATE + days_to_maturity lebih informatif
- INTEREST_RATE: tidak berubah sepanjang kontrak, bukan signal perilaku,
  sudah ter-capture oleh PRODUCT_TYPE dan total_ots

---

## 10. CARA MELANJUTKAN DI SESI BARU

Gunakan primer prompt berikut di awal sesi Claude baru:

---

**[PRIMER PROMPT — copy-paste ke awal sesi baru]**

```
Saya sedang mengerjakan proyek CollectAI — sistem AI untuk debt collection.

Saya sudah memiliki sesi panjang sebelumnya yang menghasilkan arsitektur lengkap
untuk sistem ini. Saya akan upload beberapa dokumen agar Anda bisa memahami
konteks penuh dan melanjutkan pekerjaan dari titik yang sudah ada.

File yang akan saya upload:
1. CollectAI_Handoff.md (dokumen ini) — ringkasan lengkap semua keputusan
2. CollectAI_System_Rules.md — skema tabel, formula, business rules
3. CollectAI_Scoring_Engine.md — kode scoring lengkap
4. CollectAI_MLOps_Pipeline.md — kode MLOps lengkap
5. CollectAI_Agent_Tasks.md — 30 task yang sudah selesai (T01–T30)
6. CollectAI_Data_Upgrade_Tasks.md — 17 task upgrade yang belum dikerjakan (T31–T47)

Status saat ini:
- TASK-01 sampai TASK-30 sudah selesai dikerjakan oleh AI agent
- TASK-31 sampai TASK-47 belum dikerjakan

Yang perlu dilanjutkan:
[Isi sesuai kebutuhan Anda, contoh:]
- Memulai eksekusi TASK-31 sampai TASK-47
- Review kode dari task tertentu
- Diskusi arsitektur lebih lanjut
- [atau kebutuhan lain]

Mohon baca semua dokumen yang saya upload, konfirmasi pemahaman Anda,
dan kita lanjutkan dari sana.
```

---

*Dokumen ini dibuat sebagai project handoff dari sesi Claude (claude.ai personal)
ke sesi Claude (Claude Team / Office) untuk kelanjutan proyek CollectAI.*