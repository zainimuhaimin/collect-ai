# CollectAI — System Rules, Formula & Daily Update Flow
> Dokumen ini mendefinisikan skema tabel output, formula feature engineering, business rules,
> dan prosedur refresh harian. Diperbarui setiap ada perubahan logika bisnis atau threshold.

---

## DAFTAR ISI
1. [Skema Tabel Output](#1-skema-tabel-output)
2. [Feature Engineering](#2-feature-engineering)
3. [Business Rules — Collection Analysis](#3-business-rules--collection-analysis)
4. [Business Rules — Customer Analysis](#4-business-rules--customer-analysis)
5. [Daily Batch Flow](#5-daily-batch-flow)
6. [Quality Check & Validasi](#6-quality-check--validasi)
7. [Catatan Threshold & Konfigurasi](#7-catatan-threshold--konfigurasi)

---

## 1. Skema Tabel Output

### 1.1 Collection Analysis
Granularitas: **1 baris per CONTRACT_NO aktif**
Di-refresh: setiap hari (batch malam) atau triggered saat event pembayaran baru masuk

| Kolom | Tipe | Deskripsi |
|---|---|---|
| `CONTRACT_NO` | VARCHAR | PK — FK ke Contract Snapshot |
| `CUST_ID` | VARCHAR | FK ke Customer Master |
| `RECOVERY_SCORE` | FLOAT (0.00–1.00) | Probabilitas nasabah akan bayar dalam N hari |
| `RISK_SEGMENT` | VARCHAR | Self-cure / Can Pay / Cannot Pay / Won't Pay |
| `NBA_RECOMMENDATION` | VARCHAR | WA / Deskcoll / Visit / Somasi / Pickup |
| `PRIORITY_LEVEL` | VARCHAR | Critical / High / Medium / Low |
| `CONFIDENCE_LEVEL` | FLOAT (0.00–1.00) | Tingkat keyakinan model terhadap RECOVERY_SCORE |
| `SCORING_DATE` | DATE | Tanggal scoring dilakukan |

---

### 1.2 Customer Analysis
Granularitas: **1 baris per CUST_ID** — mengagregasi SEMUA kontrak (aktif & historis)
Di-refresh: mingguan + triggered saat kontrak closed

> **Koreksi dari versi sebelumnya:**
> - ❌ Hapus `LAST_CONTRACT_NO` — tidak representatif untuk nasabah multi-kontrak
> - ✅ Tambah `ACTIVE_CONTRACT_COUNT` — jumlah kontrak aktif saat ini
> - ✅ Tambah `TOTAL_ACTIVE_OTS` — total beban hutang aktual nasabah
> - ✅ `PTP_RELIABILITY_INDEX` dihitung lintas semua kontrak, bukan per kontrak
> - ✅ `COLLECTION_SENSITIVITY` dihitung dari seluruh riwayat interaksi nasabah

| Kolom | Tipe | Deskripsi |
|---|---|---|
| `CUST_ID` | VARCHAR | PK — FK ke Customer Master |
| `ACTIVE_CONTRACT_COUNT` | INT | Jumlah kontrak aktif saat ini |
| `TOTAL_ACTIVE_OTS` | DECIMAL | SUM(PRNC_OTS + INTR_OTS) semua kontrak aktif |
| `BEHAVIORAL_GRADE` | CHAR(1) | A / B / C / D — agregasi historis lintas semua kontrak |
| `RECOVERY_EFFORT_LEVEL` | VARCHAR | Low / Mid / High — effort collector yang dibutuhkan |
| `PTP_RELIABILITY_INDEX` | FLOAT (0.0–1.0) | Rasio PTP yang ditepati lintas semua kontrak |
| `COLLECTION_SENSITIVITY` | VARCHAR | Channel paling efektif untuk nasabah ini |
| `B_LIST_STATUS` | CHAR(1) | Y / N — nasabah bermasalah (lihat rules di bawah) |
| `UPDATE_TIMESTAMP` | DATETIME | Timestamp terakhir AI memperbarui profil ini |

---

## 2. Feature Engineering

Feature engineering dibagi menjadi dua level. **Contract-Level** menjadi input ke Collection Analysis.
**Customer-Level** menjadi input ke Customer Behavioral Standing DAN sebagai enrichment ke AI scoring.

---

### 2.1 Contract-Level Features
> Join pattern:
> ```sql
> FROM contract_snapshot cs
> LEFT JOIN payment_history ph ON cs.contract_no = ph.contract_no
> LEFT JOIN lkp_interaction li  ON cs.contract_no = li.contract_no
> GROUP BY cs.contract_no
> ```

| Feature | Rumus |
|---|---|
| `dpd_current` | `cs.DPD_CURRENT` langsung dari Contract Snapshot |
| `cycle_encoded` | `CASE WHEN CYCLE_AKHIR='C0' THEN 0 WHEN CYCLE_AKHIR='C1' THEN 1 WHEN CYCLE_AKHIR='C2' THEN 2 ELSE 3 END` |
| `total_ots` | `cs.PRNC_OTS + cs.INTR_OTS` |
| `payment_rate` | `COUNT(ph.PAY_STATUS = 'Full') / NULLIF(COUNT(ph.PAYMENT_ID), 0)` |
| `partial_rate` | `COUNT(ph.PAY_STATUS = 'Partial') / NULLIF(COUNT(ph.PAYMENT_ID), 0)` |
| `avg_delay_days` | `AVG(ph.DELAY_DAYS)` — NULL jika belum ada pembayaran |
| `days_since_last_pay` | `DATEDIFF(TODAY, MAX(ph.ACTUAL_PAY_DATE))` — NULL jika belum pernah bayar |
| `total_ptp_made` | `COUNT(li.RESULT_CODE = 'PTP')` |
| `total_ptp_kept` | `COUNT(li.RESULT_CODE = 'PTP') WHERE EXISTS pembayaran dalam 7 hari setelah PROMISE_DATE` |
| `ptp_fulfillment_rate` | `total_ptp_kept / NULLIF(total_ptp_made, 0)` — range 0.0–1.0 |
| `avg_interaction_score` | `AVG(li.INTERACTION_SCORE)` — range 1–5 |
| `last_result_code` | `li.RESULT_CODE WHERE ACTION_DATE = MAX(ACTION_DATE)` — hasil interaksi terakhir |
| `treatment_count` | `COUNT(li.LKP_ID)` — total berapa kali sudah dicontact |
| `rejection_count` | `COUNT(li.RESULT_CODE IN ('Menolak', 'Tidak Bisa Dihubungi'))` |

---

### 2.2 Customer-Level Features
> Join pattern:
> ```sql
> FROM customer_master cm
> JOIN contract_snapshot cs      ON cm.cust_id = cs.cust_id
> JOIN payment_history ph        ON cs.contract_no = ph.contract_no
> JOIN lkp_interaction li        ON cs.contract_no = li.contract_no
> GROUP BY cm.cust_id
> ```

| Feature | Rumus |
|---|---|
| `active_contract_count` | `COUNT(cs.CONTRACT_NO) WHERE status = 'aktif'` |
| `total_active_ots` | `SUM(cs.PRNC_OTS + cs.INTR_OTS) WHERE status = 'aktif'` |
| `ptp_reliability_index` | `SUM(total_ptp_kept per kontrak) / NULLIF(SUM(total_ptp_made per kontrak), 0)` lintas semua kontrak |
| `broken_ptp_count` | `SUM(total_ptp_made - total_ptp_kept)` lintas semua kontrak |
| `delay_trend` | Slope linier dari AVG(DELAY_DAYS) per bulan dalam 6 bulan terakhir. `> 0` = memburuk, `≤ 0` = stabil/membaik |
| `channel_effectiveness` | `MODE(li.TREATMENT_TYPE) WHERE li.RESULT_CODE = 'Bayar'` lintas semua kontrak. Jika tie: prioritas urutan termurah (WA > Deskcoll > Visit > Somasi) |
| `historical_default_count` | `COUNT(DISTINCT cs.CONTRACT_NO) WHERE MAX(CYCLE_AKHIR) IN ('C3', 'C3+')` per CUST_ID (termasuk kontrak historis/closed) |
| `income_proxy` | `CASE WHEN CUST_INCOME_LEVEL='Low' THEN 3000000 WHEN CUST_INCOME_LEVEL='Mid' THEN 8000000 WHEN CUST_INCOME_LEVEL='High' THEN 20000000 END` |
| `income_debt_ratio` | `total_active_ots / income_proxy` — semakin tinggi = semakin tertekan kapasitas bayar |
| `composite_behavioral_score` | Lihat rumus di bawah (digunakan untuk BEHAVIORAL_GRADE) |

#### Rumus `composite_behavioral_score`

Dihitung per CUST_ID menggunakan weighted average dari fitur-fitur perilaku, dengan **recency weighting** (kontrak lebih baru diberi bobot lebih tinggi):

```
composite_behavioral_score =
    (payment_rate_weighted     × 0.30)
  + (ptp_reliability_index     × 0.25)
  + (interaction_score_norm    × 0.20)
  + (delay_score               × 0.25)
```

Keterangan per komponen:
```
payment_rate_weighted     = AVG(payment_rate per kontrak, weighted by recency)
                            bobot: kontrak terbaru = 1.0, sebelumnya = 0.7, dst.

ptp_reliability_index     = sudah dihitung di atas (lintas kontrak)

interaction_score_norm    = (AVG(INTERACTION_SCORE) - 1) / 4
                            normalisasi dari skala 1–5 ke skala 0.0–1.0

delay_score               = MAX(0, 1 - (avg_delay_days / 90))
                            0 hari terlambat = 1.0, ≥ 90 hari = 0.0
```

---

## 3. Business Rules — Collection Analysis

### 3.1 RECOVERY_SCORE
Dihasilkan oleh model ML (Gradient Boosting). Input features:

```
Input wajib (contract-level):
  dpd_current, cycle_encoded, total_ots, payment_rate, avg_delay_days,
  ptp_fulfillment_rate, avg_interaction_score, days_since_last_pay,
  rejection_count, last_result_code_encoded

Input enrichment (customer-level dari CBS):
  ptp_reliability_index, delay_trend, historical_default_count,
  income_debt_ratio, active_contract_count, total_active_ots
```

### 3.2 CONFIDENCE_LEVEL
```
HIGH   (0.75–1.00) : data lengkap, ≥ 3 payment history, ≥ 2 interaksi LKP
MEDIUM (0.50–0.74) : data sebagian ada, 1–2 payment history atau 1 interaksi
LOW    (0.00–0.49) : data minim, kontrak baru, atau nasabah baru tanpa historis
```

### 3.3 RISK_SEGMENT

Rule dievaluasi **secara berurutan** (top-down, pertama yang cocok dipakai):

```
1. Won't Pay  → RECOVERY_SCORE < 0.30
               AND (rejection_count >= 2 OR last_result_code IN ('Menolak','Tidak Bisa Dihubungi'))

2. Cannot Pay → RECOVERY_SCORE >= 0.30 AND RECOVERY_SCORE < 0.50
               AND (broken_ptp_count > 0 OR income_debt_ratio > 2.0)

3. Self-cure  → RECOVERY_SCORE >= 0.70
               AND dpd_current <= 7
               AND payment_rate >= 0.80

4. Can Pay    → semua kondisi lain
               (RECOVERY_SCORE >= 0.50 atau tidak memenuhi kriteria di atas)
```

### 3.4 NBA_RECOMMENDATION

Rule berdasarkan kombinasi `RISK_SEGMENT` + `cycle_encoded`:

```
RISK_SEGMENT = 'Self-cure'
    → NBA = 'WA'
      (reminder otomatis, tidak perlu collector aktif)

RISK_SEGMENT = 'Can Pay'  AND  cycle_encoded IN (0, 1)
    → NBA = 'WA'

RISK_SEGMENT = 'Can Pay'  AND  cycle_encoded IN (2, 3)
    → NBA = 'Deskcoll'

RISK_SEGMENT = 'Cannot Pay'  AND  cycle_encoded IN (0, 1)
    → NBA = 'Deskcoll'

RISK_SEGMENT = 'Cannot Pay'  AND  cycle_encoded IN (2, 3)
    → NBA = 'Visit'
      (kunjungan langsung + negosiasi restrukturisasi)

RISK_SEGMENT = 'Won't Pay'  AND  total_ots < [THRESHOLD_OTS_RENDAH]
    → NBA = 'Visit'

RISK_SEGMENT = 'Won't Pay'  AND  total_ots >= [THRESHOLD_OTS_RENDAH]
    → NBA = 'Somasi'

RISK_SEGMENT = 'Won't Pay'  AND  total_ots >= [THRESHOLD_OTS_TINGGI]
  AND historical_default_count >= 2
    → NBA = 'Pickup'
```

> **Catatan:** Override CBS — jika `COLLECTION_SENSITIVITY` nasabah ini adalah 'Visit'
> dan NBA default adalah 'WA', maka NBA tetap menggunakan channel yang terbukti efektif
> untuk nasabah ini.

### 3.5 PRIORITY_LEVEL

Dihitung dari matriks `RISK_SEGMENT × total_ots`:

```
┌───────────────┬──────────────────┬───────────────────┬───────────────────┐
│               │  OTS Rendah      │  OTS Menengah     │  OTS Tinggi       │
│               │  (< 5 juta)      │  (5–20 juta)      │  (> 20 juta)      │
├───────────────┼──────────────────┼───────────────────┼───────────────────┤
│ Won't Pay     │  High            │  Critical         │  Critical         │
│ Cannot Pay    │  Medium          │  High             │  Critical         │
│ Can Pay       │  Low             │  Medium           │  High             │
│ Self-cure     │  Low             │  Low              │  Medium           │
└───────────────┴──────────────────┴───────────────────┴───────────────────┘
```

> Threshold OTS dapat disesuaikan per jenis produk (`PRODUCT_TYPE`) di file konfigurasi.

---

## 4. Business Rules — Customer Analysis

### 4.1 BEHAVIORAL_GRADE

Diturunkan dari `composite_behavioral_score` yang sudah dihitung di Feature Engineering:

```
Grade A  →  composite_behavioral_score >= 0.80
Grade B  →  composite_behavioral_score >= 0.60  AND < 0.80
Grade C  →  composite_behavioral_score >= 0.40  AND < 0.60
Grade D  →  composite_behavioral_score < 0.40
```

Override paksa ke Grade D jika salah satu kondisi berikut terpenuhi:
```
- broken_ptp_count >= 5  (banyak ingkar janji)
- historical_default_count >= 3  (pola kronis)
- ptp_reliability_index < 0.10  (hampir tidak pernah menepati PTP)
```

### 4.2 RECOVERY_EFFORT_LEVEL

```
Low   →  BEHAVIORAL_GRADE = 'A'
Mid   →  BEHAVIORAL_GRADE IN ('B', 'C')
High  →  BEHAVIORAL_GRADE = 'D'
        OR B_LIST_STATUS = 'Y'
        OR active_contract_count >= 3  (banyak kontrak = effort koordinasi lebih tinggi)
```

### 4.3 PTP_RELIABILITY_INDEX

```
= SUM(total_ptp_kept per kontrak)
  / NULLIF(SUM(total_ptp_made per kontrak), 0)

Jika total_ptp_made = 0 (belum pernah buat PTP):
  → nilai = NULL, bukan 0
    (0 berarti pernah buat PTP tapi tidak ditepati; NULL = belum ada data)
```

### 4.4 COLLECTION_SENSITIVITY

```
= TREATMENT_TYPE yang paling sering menghasilkan RESULT_CODE = 'Bayar'
  di seluruh riwayat LKP nasabah ini (lintas semua kontrak)

Jika tidak ada historis pembayaran setelah interaksi:
  → gunakan default dari CUST_SEGMENT:
    Segment 'Low Risk'    → default 'WA'
    Segment 'Medium Risk' → default 'Deskcoll'
    Segment 'High Risk'   → default 'Visit'

Jika ada tie (dua channel sama efektif):
  → prioritas channel termurah: WA > Deskcoll > Visit > Somasi > Pickup
```

### 4.5 B_LIST_STATUS

Di-set ke `'Y'` jika **salah satu** kondisi berikut terpenuhi:

```
Kondisi 1: BEHAVIORAL_GRADE = 'D'
Kondisi 2: broken_ptp_count >= 5
Kondisi 3: Pernah ada TREATMENT_TYPE = 'Somasi Hukum' atau 'Pickup' di riwayat LKP
Kondisi 4: historical_default_count >= 3
Kondisi 5: ptp_reliability_index < 0.10 AND total_ptp_made >= 3
              (pernah buat PTP banyak tapi hampir tidak pernah ditepati)
```

Di-set ke `'N'` jika tidak ada kondisi di atas yang terpenuhi.

> **Sekali `B_LIST_STATUS = 'Y'`, tidak otomatis kembali ke 'N'.**
> Reset ke 'N' harus melalui persetujuan manual supervisor setelah evaluasi.

### 4.6 ACTIVE_CONTRACT_COUNT & TOTAL_ACTIVE_OTS

```
ACTIVE_CONTRACT_COUNT = COUNT(CONTRACT_NO) WHERE kontrak masih aktif per CUST_ID

TOTAL_ACTIVE_OTS      = SUM(PRNC_OTS + INTR_OTS)
                        WHERE kontrak masih aktif per CUST_ID

Jika ACTIVE_CONTRACT_COUNT = 0:
  → TOTAL_ACTIVE_OTS = 0
  → CBS tetap dipertahankan untuk referensi historis
  → BEHAVIORAL_GRADE dan B_LIST_STATUS tetap berlaku untuk kontrak berikutnya
```

---

## 5. Daily Batch Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY BATCH  (tiap malam)                    │
└─────────────────────────────────────────────────────────────────┘

STEP 1 │ DATA REFRESH
       │ Tarik data terbaru dari sumber:
       │   - Contract Snapshot  → posisi DPD & OTS per hari ini
       │   - Payment History    → transaksi baru yang masuk hari ini
       │   - LKP & Interaction  → aksi penagihan yang dilakukan hari ini
       │   - Customer Master    → biasanya statis, refresh mingguan
       │
       ▼
STEP 2 │ COMPUTE CONTRACT-LEVEL FEATURES
       │ Untuk setiap CONTRACT_NO yang aktif:
       │   - Hitung semua 13 fitur contract-level (lihat Bagian 2.1)
       │   - Simpan ke tabel staging: stg_contract_features
       │
       ▼
STEP 3 │ COMPUTE CUSTOMER-LEVEL FEATURES & UPDATE CBS
       │ Untuk setiap CUST_ID yang kontraksnya berubah hari ini:
       │   - Hitung semua fitur customer-level (lihat Bagian 2.2)
       │   - Hitung composite_behavioral_score
       │   - Terapkan rules BEHAVIORAL_GRADE, RECOVERY_EFFORT_LEVEL,
       │     PTP_RELIABILITY_INDEX, COLLECTION_SENSITIVITY, B_LIST_STATUS
       │   - UPDATE tabel customer_behavioral_standing
       │   - Set UPDATE_TIMESTAMP = NOW()
       │
       │   ⚠️  Catatan: Hanya update CUST_ID yang ada perubahan data.
       │       CUST_ID tanpa perubahan tidak perlu di-recompute.
       │
       ▼
STEP 4 │ AI SCORING — RECOVERY SCORE
       │ Untuk setiap CONTRACT_NO aktif:
       │   - Gabungkan stg_contract_features + CBS terbaru
       │   - Jalankan model Gradient Boosting → hasilkan RECOVERY_SCORE
       │     dan CONFIDENCE_LEVEL
       │   - Simpan ke tabel staging: stg_ai_scores
       │
       ▼
STEP 5 │ APPLY BUSINESS RULES
       │ Untuk setiap CONTRACT_NO di stg_ai_scores:
       │   - Tentukan RISK_SEGMENT     (lihat Rules 3.3)
       │   - Tentukan NBA_RECOMMENDATION (lihat Rules 3.4)
       │     → termasuk cek override dari COLLECTION_SENSITIVITY di CBS
       │   - Tentukan PRIORITY_LEVEL   (lihat Rules 3.5)
       │
       ▼
STEP 6 │ QUALITY CHECK
       │ Validasi output sebelum di-publish (lihat Bagian 6)
       │
       ▼
STEP 7 │ PUBLISH OUTPUT
       │   - UPSERT ke tabel collection_analysis
       │     (insert baru atau update jika CONTRACT_NO sudah ada)
       │   - Set SCORING_DATE = TODAY
       │   - Log jumlah record yang diproses & distribusi RISK_SEGMENT
       │
       ▼
STEP 8 │ ALERT & NOTIFIKASI
       │   - Kirim ringkasan ke supervisor:
       │     total kontrak scored, breakdown Critical/High/Medium/Low,
       │     jumlah nasabah masuk B-List hari ini (jika ada)
       │   - Jika ada anomali dari QC → kirim alert ke tim data
```

---

### 5.1 Triggered Refresh (Non-Batch)

Selain batch harian, sistem perlu melakukan refresh parsial saat:

| Event | Aksi |
|---|---|
| Pembayaran baru masuk (`PAY_STATUS = 'Full'`) | Re-score CONTRACT_NO tersebut segera (hari yang sama) |
| Collector input PTP baru di LKP | Update `total_ptp_made` untuk kontrak terkait |
| Kontrak di-closed / lunas | Update CBS untuk CUST_ID terkait (kurangi `ACTIVE_CONTRACT_COUNT` dan `TOTAL_ACTIVE_OTS`) |
| Supervisor manual override B_LIST | Update CBS langsung, flag sebagai `MANUAL_OVERRIDE = Y` |

---

## 6. Quality Check & Validasi

Dijalankan di **Step 6** sebelum publish. Jika ada yang gagal, proses dihentikan dan alert dikirim.

### 6.1 Validasi Data
```
[ ] Tidak ada CONTRACT_NO duplikat di output collection_analysis
[ ] Tidak ada CUST_ID duplikat di output customer_behavioral_standing
[ ] RECOVERY_SCORE semua dalam range 0.00–1.00
[ ] CONFIDENCE_LEVEL semua dalam range 0.00–1.00
[ ] PTP_RELIABILITY_INDEX semua dalam range 0.00–1.00 atau NULL
[ ] TOTAL_ACTIVE_OTS >= 0 untuk semua CUST_ID
[ ] ACTIVE_CONTRACT_COUNT >= 0 untuk semua CUST_ID
```

### 6.2 Validasi Distribusi
```
[ ] Persentase Won't Pay tidak > 30% dari total kontrak
    → jika > 30%, kemungkinan ada bug di scoring — investigasi sebelum publish

[ ] Persentase Self-cure tidak < 5% dari total kontrak
    → jika < 5%, kemungkinan model terlalu konservatif

[ ] Jumlah Critical tidak > 20% dari total kontrak
    → jika > 20%, validasi apakah OTS threshold perlu disesuaikan

[ ] Perubahan distribusi RISK_SEGMENT vs hari sebelumnya tidak > 15%
    → perubahan drastis = indikasi data issue atau model issue
```

### 6.3 Validasi Konsistensi
```
[ ] Setiap CONTRACT_NO di collection_analysis harus punya CUST_ID
    yang ada di customer_behavioral_standing

[ ] COLLECTION_SENSITIVITY di CBS harus merupakan nilai valid:
    WA / Deskcoll / Visit / Somasi / Pickup

[ ] B_LIST_STATUS harus 'Y' atau 'N', tidak boleh NULL
[ ] BEHAVIORAL_GRADE harus 'A', 'B', 'C', atau 'D', tidak boleh NULL
```

---

## 7. Catatan Threshold & Konfigurasi

Semua nilai threshold di bawah ini **dapat disesuaikan** tanpa mengubah kode program.
Simpan di tabel konfigurasi terpisah (`tbl_config`) agar mudah diubah.

| Parameter | Nilai Default | Keterangan |
|---|---|---|
| `PTP_DAYS_WINDOW` | 7 hari | Batas hari setelah PROMISE_DATE untuk dianggap "PTP kept" |
| `THRESHOLD_OTS_RENDAH` | 5.000.000 | Batas bawah OTS untuk priority matrix |
| `THRESHOLD_OTS_TINGGI` | 20.000.000 | Batas atas OTS untuk priority matrix |
| `BROKEN_PTP_BLACLIST` | 5 | Jumlah broken PTP untuk masuk B_LIST |
| `HISTORICAL_DEFAULT_BLACKLIST` | 3 | Jumlah kontrak C3+ untuk masuk B_LIST |
| `DELAY_TREND_WINDOW` | 6 bulan | Window historis untuk hitung delay_trend |
| `REJECTION_THRESHOLD` | 2 | Jumlah penolakan untuk klasifikasi Won't Pay |
| `SEGMENT_SHIFT_ALERT` | 15% | Batas perubahan distribusi yang memicu alert |
| `RECENCY_WEIGHT_DECAY` | 0.7 | Bobot kontrak lama vs kontrak terbaru |
| `INCOME_LOW_PROXY` | 3.000.000 | Proxy pendapatan bulanan untuk INCOME_LEVEL=Low |
| `INCOME_MID_PROXY` | 8.000.000 | Proxy pendapatan bulanan untuk INCOME_LEVEL=Mid |
| `INCOME_HIGH_PROXY` | 20.000.000 | Proxy pendapatan bulanan untuk INCOME_LEVEL=High |

---

*Dokumen ini dibuat berdasarkan analisis file `Data_Dictionary_CollectAI.xlsx`.*
*Revisi berikutnya: sesuaikan threshold setelah model divalidasi dengan data aktual.*