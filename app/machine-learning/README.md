# CollectAI — Machine Learning

Pipeline scoring dan MLOps untuk penagihan: memprediksi kemungkinan nasabah
menunggak akan membayar, menentukan segmen risiko + *Next Best Action*, menyusun
profil perilaku customer, dan menghasilkan tawaran restrukturisasi batch.

Membaca dan menulis ke **Postgres yang sama** dipakai
[`app/backend/`](../backend/README.md).

---

## Arsitektur

```
┌──────────────────────────────────────────────────────┐
│                    4 TABEL INPUT                     │
│  customer_master · contract_snapshot                 │
│  payment_history · lkp_interaction                   │
└────────────────────────┬─────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  src/feature_engineering.py  │
          │  fitur level kontrak +       │
          │  agregat level customer      │
          │  ⚠ guard feature_cutoff:     │
          │    data ≤ ref_date − 30 hari │
          └──────────────┬──────────────┘
                         │
     ┌───────────────────┼───────────────────┐
     ▼                   ▼                   ▼
┌──────────┐  ┌────────────────────┐  ┌────────────────┐
│ 4 model  │  │ src/business_rules │  │ src/cbs_builder│
│ XGBoost  │  │ risk segment, NBA, │  │ grade A-D,     │
│          │  │ priority level     │  │ sensitivity    │
└────┬─────┘  └─────────┬──────────┘  └───────┬────────┘
     └──────────────────┼─────────────────────┘
                        │
     ┌──────────────────▼──────────────────┐
     │ src/scoring_engine.py               │
     │ inferensi + quality check (QC)      │
     └──────────────────┬──────────────────┘
                        │
   ┌────────────────────┴────────────────────┐
   ▼                                          ▼
┌────────────────────────┐  ┌──────────────────────────────┐
│ ai_intelligence_output │  │ customer_behavioral_standing │
│ (skor per kontrak)     │  │ (CBS — profil perilaku)      │
└───────────┬────────────┘  └──────────────┬───────────────┘
            └───────────────┬──────────────┘
                            ▼
        ┌───────────────────────────────────────┐
        │ pipelines/restructuring_runner.py     │
        │ + app/shared/..._offer_calculator.py  │
        │ ──► restructuring_recommendation_output│
        └───────────────────────────────────────┘
```

---

## Empat model, satu label

| Model | Fitur | Peran | Wajib? |
|---|---|---|---|
| `recovery` | **36** | Skor pemulihan utama — dasar segmentasi & prioritas | **Ya.** `daily_scoring.py` raise `FileNotFoundError` tanpa champion-nya |
| `self_cure` | 12 | Kemungkinan pulih sendiri tanpa intervensi | Tidak (*soft-degrade* ⇒ kolom `NULL`) |
| `roll_forward` | 14 | Risiko naik ke bucket DPD berikutnya | Tidak |
| `ptp_success` | 11 | Kemungkinan janji bayar (PTP) ditepati | Tidak |

Set fitur per model ada di `MODEL_TYPE_FEATURE_COLS` (`config/settings.py`).

**Keempatnya memakai satu label yang sama:** `actual_paid` — bernilai 1 kalau
kontrak punya baris `payment_history` dengan `pay_status ∈ {Full, Partial}` di
dalam jendela `[reference_date − 30d, reference_date]`
(`src/outcome_labeler.py`). Label per-model yang berbeda-beda (`self_cure_flag`,
`cycle` vs `prev_cycle`, `ptp_status == 'KEPT'`) pernah didesain tapi **belum
pernah diimplementasikan** — jadi perbedaan antar model saat ini murni datang dari
**set fitur** dan **populasi training**-nya, bukan dari target yang berbeda.

⚠️ **`roll_forward_risk` tersimpan dalam bentuk terbalik** — nilainya P(*tidak*
bayar), bukan P(bayar). Lihat komentar di `src/scoring_engine.py`. Jangan
menafsirkannya mentah tanpa memperhatikan ini.

---

## Quick start

```bash
# 1. Dependency (venv yang sama dipakai backend/faker — lihat README root)
source ../../.venv/bin/activate
pip install -r requirements.txt
#    macOS: brew install libomp   (XGBoost butuh OpenMP runtime)

# 2. Schema database
#    (untuk init dari nol seluruh project sekaligus, cukup jalankan ../../schema.sql
#    dari root — file ini + tabel backend sudah tergabung di sana)
psql -d collect_ai -f config/schema_combined.sql

# 3. Data sintetis (dari root repo)
cd ../../faker && python generate-faker-realistic.py --reset && cd ../app/machine-learning

# 4. Latih keempat model
python pipelines/train_initial_model.py    # recovery
python pipelines/train_self_cure.py
python pipelines/train_roll_forward.py
python pipelines/train_ptp_success.py

# 5. Scoring — menghasilkan ke-4 skor sekaligus dalam 1 run
python pipelines/daily_scoring.py

# 6. Opsional: monitoring/drift dan tawaran restrukturisasi
python pipelines/weekly_mlops.py
python pipelines/restructuring_runner.py
```

Kredensial database dibaca dari `.env` di **root repo**
(`PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE`), atau bisa di-override
seluruhnya lewat `COLLECTAI_DB_URL`.

> Direktori `models/` **tidak ada** di repo bersih — ia dibuat saat training
> pertama, bersama `registry.json`. Alternatif dari langkah 4–6: klik tombol
> **Sync** di halaman AI Intelligence, yang menjalankan training-if-missing →
> scoring → monitoring lewat subprocess.

### File schema

Diterapkan berurutan; semuanya idempoten. **Tidak ada migration framework** —
penambahan kolom dilakukan dengan `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

| File | Isi |
|---|---|
| `config/schema_combined.sql` | **Pakai ini** untuk instalasi fresh ML saja. Untuk init seluruh project sekaligus (ML + backend), pakai `schema.sql` di root repo — gabungan file ini + `app/backend/db/schema_*.sql` |
| `config/schema.sql` | Versi awal (historis) |
| `config/schema_v2.sql` · `v3` · `v4` | Penambahan bertahap (`v3`: `cust_name`, `v4`: `contract_snapshot.status`) |
| `config/schema_v5.sql` | `historical_default_count`/`income_debt_ratio` (dulu selalu 0, lihat batasan #1) + `ai_intelligence_output.nba_trigger` (cabang NBA mana yang menang) |
| `config/schema_v6.sql` | Hapus channel `SMS`, lebur ke `WA` (lihat batasan #3) |

---

## Struktur berkas

```text
app/machine-learning/
├── config/
│   ├── settings.py              # SEMUA threshold, hyperparameter, feature set
│   └── schema*.sql              # DDL (lihat tabel di atas)
├── src/
│   ├── feature_engineering.py   # ekstraksi fitur + guard anti-leakage
│   ├── chunked_features.py      # baca+agregasi per-batch cust_id (RAM konstan
│   │                             # terhadap N) — dipakai daily_scoring/train_*/
│   │                             # weekly_mlops/cbs_builder, TIDAK mengubah
│   │                             # nilai fitur (lihat performance-report.md §3f)
│   ├── cbs_builder.py           # Customer Behavioral Standing
│   ├── business_rules.py        # risk segment, NBA + nba_trigger (cabang mana yang
│   │                             # menang), priority, CHANNEL_RANK
│   ├── scoring_engine.py        # inferensi + run_quality_check()
│   ├── outcome_labeler.py       # actual_paid + pelabelan skor historis
│   ├── retrain_strategies.py    # full / rolling window / recency-weighted + grouped CV
│   ├── model_registry.py        # versioning champion/challenger
│   ├── champion_challenger.py   # perbandingan & promosi
│   ├── model_monitor.py         # drift detection + tulis model_monitoring_log
│   ├── governance_config.py     # baca bobot CBS dari model_governance_config
│   ├── restructuring_eligibility.py
│   └── restructuring_offer_calculator.py   # re-export dari app/shared/ + policy dari settings
├── pipelines/
│   ├── train_initial_model.py   # recovery
│   ├── train_self_cure.py
│   ├── train_roll_forward.py
│   ├── train_ptp_success.py
│   ├── daily_scoring.py         # entry point harian (ke-4 skor sekaligus)
│   ├── weekly_mlops.py          # label, AUC live, drift, retrain, promosi
│   └── restructuring_runner.py  # batch tawaran restrukturisasi
├── models/                      # artifact .pkl + registry.json (dibuat saat training)
│   └── archive/                 # champion lama (untuk rollback)
├── logs/                        # scoring_log.csv
├── data/                        # raw/ dan samples/
└── tests/                       # 155 test, tidak butuh database
```

**Kalkulasi restrukturisasi tidak tinggal di sini.** Implementasinya ada di
`app/shared/restructuring_offer_calculator.py` — satu salinan, di-import bersama
oleh backend dan ML supaya batch dan API on-demand tidak bisa memberi angka
berbeda. `src/restructuring_offer_calculator.py` hanya re-export + fungsi
`restructuring_policy_from_settings()`.

---

## Konfigurasi

Semua aturan bisnis, threshold, dan hyperparameter terpusat di
`config/settings.py`. Ubah nilainya, jalankan `daily_scoring.py` lagi — tidak
perlu menyentuh kode inti.

Nilai kunci saat ini:

| Konstanta | Nilai | Arti |
|---|---|---|
| `TARGET_COL` | `actual_paid` | Label tunggal keempat model |
| `LABEL_WINDOW_DAYS` | 30 | Jendela label, sekaligus jarak *feature cutoff* |
| `PTP_DAYS_WINDOW` | 7 | Toleransi hari untuk menilai PTP ditepati |
| `CV_N_SPLITS` | 5 | Fold cross-validation |
| `MIN_CV_AUC_TO_DEPLOY` | 0.50 | Gate minimum AUC untuk deploy |
| `AUC_FLOOR` | 0.68 | Di bawah ini, `weekly_mlops` memicu retrain |
| `XGB_N_ESTIMATORS` / `XGB_MAX_DEPTH` | 500 / 6 | Lihat [batasan](#batasan-yang-diketahui) |
| `STRICT_QC` | `False` | Cek distribusi jadi soft-warning (lihat di bawah) |

Beberapa nilai bisa di-override lewat env var di `.env` root, mis.
`COLLECTAI_STRICT_QC=true`.

⚠️ Mengubah `FEATURE_COLS` atau `TARGET_COL` **mewajibkan training ulang**.

**Bobot CBS** tidak diubah lewat file: nilainya dibaca dari tabel
`model_governance_config` (`src/governance_config.py`), yang bisa diedit dari UI
halaman AI Intelligence tanpa deploy — lengkap dengan audit trail. Kalau tabelnya
belum ada isinya, sistem jatuh ke default di `settings.py`.

### Quality check: hard vs soft

`run_quality_check()` (`src/scoring_engine.py`) memisahkan dua jenis
pemeriksaan:

- **Selalu hard-fail** — integritas data: range skor 0–1, kolom wajib tidak
  `NULL`, `contract_no` tidak duplikat. Ini bug nyata di kode/data.
- **Soft-warning secara default** — distribusi segmen (`wont_pay_pct`,
  `self_cure_pct`, `critical_pct`). Batas `QC_*_PCT` itu **asumsi komposisi
  portfolio, bukan invariant kebenaran pipeline**. Kalau mix portfolio bergeser,
  menggagalkan seluruh run berarti nol skor tersimpan — jauh lebih merusak
  daripada skor dengan komposisi tak terduga. Pelanggaran tetap dicetak beserta
  nilai aktualnya.

Aktifkan hard-fail eksplisit dengan `COLLECTAI_STRICT_QC=true`, atau
`run_daily_scoring(strict_qc=True)`.

---

## Evaluasi model: bagaimana AUC dihitung

Ini pernah salah dan penting untuk tidak terulang.

**Grouped cross-validation, bukan split biasa.** `_cross_validate()`
(`src/retrain_strategies.py`) memakai `StratifiedGroupKFold` yang dikelompokkan
per `cust_id`. Kontrak dari satu customer berbagi parameter perilaku yang sama,
jadi split biasa akan membocorkan informasi antar-fold dan menaikkan estimasi
secara palsu.

**AUC yang dilaporkan bukan in-sample.** `strategy_recency_weighted` dulu
melaporkan AUC pada irisan `df[months_ago <= 1]` — dan karena
`build_target_variable()` memberi **satu** `scoring_date` konstan ke semua baris,
irisan itu adalah **seluruh training set**. Jadi angkanya adalah AUC in-sample
pada model yang baru saja di-fit, bukan estimasi generalisasi. Sekarang yang
dilaporkan dan di-gate adalah AUC grouped-CV; model yang di-deploy tetap di-fit
atas semua baris dengan bobot recency.

**Angka acuan sehat** pada dataset sintetis 2000 customer:

| Model | AUC grouped-CV | n |
|---|---|---|
| `recovery` | ~0.80 | 2918 |
| `self_cure` | ~0.70 | 1728 |
| `roll_forward` | ~0.68 | 1673 |
| `ptp_success` | ~0.73 | 2497 |

Kalau `recovery` mendekati **0.95+**, itu hampir pasti kebocoran data, bukan
model yang bagus — jalankan `faker/validate_leakage.py`.

**Dua AUC yang berbeda, jangan tertukar:**

| | Sumber | Arti |
|---|---|---|
| AUC training | `registry.json` | Cross-validation saat model dilatih |
| AUC **live** | `model_monitoring_log` | Skor lampau dibandingkan pembayaran nyata 30 hari sesudahnya |

AUC live baru terisi setelah ada **≥30 hari riwayat scoring** — sebelum itu
`scoring_labels` kosong dan `model_monitor` menyimpan `auc=NULL`. Ini normal di
instalasi baru, bukan tanda monitoring rusak. Hitungan drift tetap nyata sejak
run pertama.

---

## Penjadwalan

| Pipeline | Kapan | Yang dilakukan |
|---|---|---|
| `daily_scoring.py` | Harian, ~23:00 (setelah transaksi hari itu selesai) | Hitung fitur terbaru, inferensi ke-4 model, terapkan business rules, publish ke `ai_intelligence_output`; bootstrap CBS kalau tabelnya masih kosong |
| `weekly_mlops.py` | Mingguan, Minggu malam / Senin ~01:00 | Labeli skor yang sudah jatuh tempo, hitung AUC live champion, deteksi drift, picu retrain, promosikan challenger; tulis `model_monitoring_log` |
| `restructuring_runner.py` | Harian, setelah `daily_scoring` | Generate tawaran restrukturisasi + QC-nya |

Tombol **Sync** di backend menjalankan urutan: `train_*` (untuk model yang belum
punya champion) → `daily_scoring` → `weekly_mlops`. `weekly_mlops` **selalu**
dijalankan, karena drift dihitung dari hasil scoring sehingga harus mengikuti
setiap scoring baru.

> `daily_scoring.py` menulis CBS **hanya kalau tabelnya kosong**
> (bootstrap sekali, bukan refresh harian). Jadi `behavioral_grade`,
> `ptp_reliability_index`, dan `b_list_status` bisa lebih basi daripada skornya.

---

## Retraining & champion/challenger

Retrain dipicu `weekly_mlops.py` kalau salah satu terpenuhi:

1. AUC live champion turun di bawah `AUC_FLOOR` (0.68).
2. Drift masif — jumlah fitur dengan pergeseran distribusi kritis mencapai
   `N_CRITICAL_DRIFT_TRIGGER`.
3. Model sudah terlalu lama tidak diperbarui.

Prosesnya: retrain dengan `strategy_recency_weighted` (bobot lebih tinggi untuk
data terbaru) → daftarkan sebagai **challenger** → evaluasi *shadow mode*
berdampingan dengan champion → promosikan otomatis jika AUC-nya mengungguli
champion setidaknya `MIN_AUC_IMPROVEMENT`. Champion lama dipindah ke
`models/archive/` untuk rollback.

Tiga strategi tersedia di `src/retrain_strategies.py`:
`strategy_full_retrain`, `strategy_rolling_window(months=6)`,
`strategy_recency_weighted` (yang dipakai keempat pipeline).

---

## Testing

```bash
pytest tests/ -q      # 168 test, TIDAK butuh database
```

| Modul | Cakupan |
|---|---|
| `test_features.py` | Feature engineering + guard cutoff |
| `test_cbs.py` | CBS builder & grading |
| `test_rules.py` | Risk segment, NBA, priority |
| `test_scoring.py` | Scoring engine + quality check |
| `test_mlops.py` | Drift, registry, champion/challenger |
| `test_restructuring_engine.py` | Eligibility, kalkulasi tawaran, guardrail |
| `test_features_chunked.py` | Parity chunked read vs non-chunked (byte-identik, semua kombinasi param) |

---

## Batasan yang diketahui

1. **Dua fitur selalu bernilai 0** di training maupun scoring: `delay_trend`,
   `broken_ptp_count` — karena `out_cols` di `cbs_builder.build_cbs()` tidak
   pernah mengembalikannya. Tidak ada jumlah data yang bisa memperbaiki ini.
   (`historical_default_count`/`income_debt_ratio` **sudah diperbaiki** di
   `schema_v5.sql` — keduanya sudah dihitung benar sejak awal di
   `compute_customer_features()`, hanya dibuang di `out_cols`; NBA `Pickup`
   sekarang bisa terpicu.)
2. **`restructure_count` selalu 0** — satu-satunya yang menghitungnya,
   `cbs_builder.update_cbs()`, tidak punya pemanggil produksi.
3. ~~`SMS` hilang dari dua peta ranking channel~~ — **sudah diperbaiki**
   (`schema_v6.sql`): channel `SMS` dihapus sepenuhnya dari sistem, dilebur ke
   `WA`. `RECOVERY_SOURCE_MAP` sekarang selaras dengan `CHANNEL_RANK`.
4. **`XGB_N_ESTIMATORS=500, XGB_MAX_DEPTH=6` over-parameterized** untuk ~2.900
   baris / 36 fitur. Terlihat dari *placebo test*: bahkan dengan label acak,
   model `recovery` masih menunjukkan AUC di atas 0.50.
5. **`MIN_CV_AUC_TO_DEPLOY = 0.50`** jauh di bawah 0.70 yang tertulis di
   `scoring-engine.md`. Dibiarkan rendah secara sengaja supaya AUC yang sudah
   dihitung jujur tidak langsung memblokir training.
6. **`contract_snapshot` tidak punya `snapshot_date`** dan tidak difilter oleh
   guard cutoff — hanya `payment_history`/`lkp_interaction` yang dibatasi. Ini
   celah point-in-time struktural; generator data mengompensasinya dengan
   membangun snapshot pada posisi cutoff (lihat [`faker/README.md`](../../faker/README.md)).
7. **`'Overpaid'` tidak terlihat oleh konsumen mana pun** — tidak dihitung
   positif oleh `outcome_labeler.py`, tidak masuk `payment_rate` di
   `feature_engineering.py`.
8. `helpers/database.py` di faker membaca env `PG*` sementara `config/settings.py`
   juga menghormati `COLLECTAI_DB_URL` — generator dan pipeline **bisa menunjuk
   database berbeda** kalau keduanya diset tidak konsisten.

---

## Troubleshooting

**`xgboost.core.XGBoostError: libomp.dylib not found` (macOS)**
→ `brew install libomp`.

**`FileNotFoundError: Champion model belum tersedia`**
→ Model `recovery` belum pernah dilatih. `python pipelines/train_initial_model.py`.

**`ValueError: AUC 0.48 di bawah threshold 0.50`**
→ Data training terlalu sedikit atau polanya acak. Tambah volume data, atau
periksa proporsi label `actual_paid` tidak sangat timpang.

**`ValueError: Terdapat NULL pada recovery_score`**
→ Artifact model rusak, atau ada kolom di `FEATURE_COLS` yang tidak bisa
dikonversi ke numerik. Pastikan `compute_contract_features` hanya menghasilkan
float/int, lalu retrain.

**`ValueError: QC hard-fail: duplicate_contract_no`**
→ Ada baris duplikat `contract_no` di `contract_snapshot`. Satu kontrak = satu
baris skor; hapus duplikasinya di level tabel.

**`ValueError: QC hard-fail: wont_pay_pct<=30%, critical_pct<=20%`**
→ Seharusnya tidak muncul lagi dengan default sekarang. Kalau muncul,
`COLLECTAI_STRICT_QC=true` sedang aktif atau `strict_qc=True` diteruskan
eksplisit. Lihat [Quality check](#quality-check-hard-vs-soft).

**AUC mencurigakan tinggi (≥0.95)**
→ Hampir pasti kebocoran data, bukan model bagus. Jalankan
`cd ../../faker && python validate_leakage.py`, termasuk placebo test-nya.

**`psycopg2.OperationalError: Connection refused`**
→ Postgres belum jalan, atau `.env` root menunjuk host/port yang salah. Dengan
Docker Compose, port di host adalah **5433**.
