# 🚀 CollectAI Machine Learning System

## 1. 📖 Overview
CollectAI adalah sistem kecerdasan buatan (AI) berbasis Machine Learning yang dirancang khusus untuk manajemen penagihan (debt collection). Sistem ini memprediksi *Recovery Score* (probabilitas pembayaran) dari nasabah yang menunggak dan merekomendasikan saluran komunikasi terbaik (*Next Best Action* / NBA), serta mengkategorikan prioritas penagihan secara harian. Dengan mengautomasi pengambilan keputusan, CollectAI meningkatkan efisiensi dan tingkat keberhasilan penagihan.

## 2. 🏗️ Architecture Diagram

```ascii
┌─────────────────────────────────────────┐
│              INPUT TABLES               │
│ 1. customer_master (Profil Nasabah)     │
│ 2. contract_snapshot (Data Pinjaman)    │
│ 3. payment_history (Riwayat Pembayaran) │
│ 4. lkp_interaction (Log Interaksi)      │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         FEATURE ENGINEERING             │
│ Ekstraksi 21 fitur (Contract & Customer)│
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│            AI ENGINE (XGBoost)          │
│ Prediksi Probabilitas & Aturan Bisnis   │
└─────────┬─────────────────────┬─────────┘
          │                     │
          ▼                     ▼
┌───────────────────┐ ┌───────────────────┐
│   OUTPUT TABLE 1  │ │   OUTPUT TABLE 2  │
│ ai_intelligence_  │ │ customer_behavior-│
│ output            │ │ al_standing (CBS) │
│ (Scoring Harian)  │ │ (Profil Perilaku) │
└───────────────────┘ └───────────────────┘
```

## 3. ⚡ Quick Start

Jalankan sistem dari nol hingga *first scoring* dengan langkah-langkah berikut:

```bash
# 1. Buat dan aktifkan virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux (Gunakan .venv\Scripts\activate untuk Windows)

# 2. Install dependencies
cd app/machine-learning
pip install --upgrade pip
pip install -r requirements.txt

# 3. Setup schema database PostgreSQL (Gunakan kredensial yang relevan)
psql -U postgres -d collect_ai -f config/schema.sql

# 4. Generate sample data (Faker)
cd ../../faker
python generate-faker-realistic.py
cd ../app/machine-learning

# 5. Latih model champion awal
python pipelines/train_initial_model.py

# 6. Jalankan daily scoring pertama
python pipelines/daily_scoring.py
```

## 4. 📂 File Structure

Penjelasan singkat tentang struktur folder dan file pada `app/machine-learning`:

```text
app/machine-learning/
├── config/
│   ├── settings.py          # Threshold, konstanta, parameter model, & config sistem
│   └── schema.sql           # DDL untuk membuat tabel input dan output di database
├── data/
│   ├── raw/                 # Folder untuk data mentah/CSV
│   └── samples/             # Folder hasil sample data generator
├── models/
│   ├── archive/             # Model lama yang digantikan (backup rollback)
│   └── registry.json        # File registrasi versi model (champion & challenger)
├── src/                     # Core system modules
│   ├── feature_engineering.py # Logika ekstraksi fitur
│   ├── cbs_builder.py       # Logika Customer Behavioral Standing
│   ├── scoring_engine.py    # Mesin utama inferensi dan quality check
│   ├── business_rules.py    # Logika NBA, Risk Segment, & Prioritas
│   ├── outcome_labeler.py   # Pembuat label actual paid/unpaid
│   ├── model_monitor.py     # Logika drift detection dan monitoring performa
│   ├── retrain_strategies.py# Pilihan strategi training (rolling window, recency)
│   └── model_registry.py    # Pengelola versioning model
├── pipelines/               # Runner utama
│   ├── train_initial_model.py # Script untuk training awal
│   ├── daily_scoring.py     # Entry point harian untuk skor seluruh kontrak aktif
│   └── weekly_mlops.py      # Entry point mingguan untuk evaluasi & retraining otomatis
├── tests/                   # Kumpulan Unit Test
└── requirements.txt         # Daftar dependency package Python
```

## 5. ⚙️ Configuration

Seluruh aturan bisnis, threshold risiko, hiperparameter model, dan *flag* sistem diatur secara terpusat di `config/settings.py`. 

**Cara mengubah threshold:**
1. Buka file `config/settings.py`.
2. Cari variabel yang relevan, misalnya untuk mengubah batas skor kategori "Won't Pay":
   ```python
   # Ubah dari 0.30 menjadi 0.25
   SCORE_THRESHOLD_WONT_PAY = 0.25
   ```
3. Simpan file. Perubahan akan langsung aktif pada *run* `daily_scoring.py` berikutnya tanpa perlu modifikasi *source code* utama.
4. *Catatan:* Perubahan pada variabel `FEATURE_COLS` atau `TARGET_COL` **mewajibkan** *retraining* model (`train_initial_model.py` atau melalui siklus `weekly_mlops.py`).

## 6. 🕒 Schedules

Untuk otomatisasi, sistem harus dijadwalkan menggunakan Cron atau Apache Airflow dengan waktu eksekusi:

1. **Daily Scoring (`pipelines/daily_scoring.py`)**
   - **Kapan:** Setiap malam pukul **23:00** (setelah seluruh transaksi hari itu selesai).
   - **Apa yang dilakukan:** Menghitung fitur terbaru, menjalankan *inference*, mengaplikasikan *business rules*, dan mem-publish rekomendasi penagihan untuk besok pagi ke tabel `ai_intelligence_output`.

2. **Weekly MLOps (`pipelines/weekly_mlops.py`)**
   - **Kapan:** Seminggu sekali, idealnya Minggu malam / Senin dini hari pukul **01:00**.
   - **Apa yang dilakukan:** Memberikan label actual *paid* untuk skor yang sudah jatuh tempo, menghitung AUC champion saat ini, memeriksa *data drift*, memicu re-training jika perlu, dan mempromosikan model *challenger* jika terbukti lebih baik.

## 7. 🔄 Model Retraining

Sistem CollectAI menerapkan MLOps berbasis **Feedback Loop otomatis**. Model diperbarui berdasarkan kondisi berikut:

- **Kapan Retraining Terpicu?** 
  Retraining akan dilakukan oleh `weekly_mlops.py` jika salah satu kondisi ini terpenuhi:
  1. Performa model (*AUC*) turun di bawah `AUC_FLOOR` (misalnya 0.68).
  2. Terjadi *data drift* yang masif (`N_CRITICAL_DRIFT_TRIGGER` tercapai, misal > 2 fitur utama distribusi datanya bergeser drastis).
  3. Model sudah terlalu lama tidak diperbarui (contoh: > 3 bulan).
- **Bagaimana Prosesnya?**
  Ketika di-trigger, sistem menjalankan *retrain* menggunakan `strategy_recency_weighted` (memberi bobot lebih tinggi pada data terbaru). Model baru didaftarkan sebagai **Challenger**. Challenger akan di-evaluasi *shadow mode* bersama Champion, dan dipromosikan otomatis menjadi Champion jika AUC-nya mengungguli Champion setidaknya sebesar `MIN_AUC_IMPROVEMENT` (misal +0.02).

## 8. 🆘 Troubleshooting

Berikut 5 error umum dan cara mengatasinya:

1. **Error:** `xgboost.core.XGBoostError: libomp.dylib not found` (khusus macOS)
   - **Penyebab:** *OpenMP runtime* yang dibutuhkan XGBoost belum ter-install.
   - **Solusi:** Jalankan `brew install libomp`.
2. **Error:** `ValueError: AUC 0.48 di bawah threshold 0.50`
   - **Penyebab:** Data training yang diberikan terlalu sedikit atau polanya acak, sehingga model tidak bisa menemukan relasi *recovery*.
   - **Solusi:** Tambahkan lebih banyak data training (jalankan script Faker lebih banyak) atau pastikan proporsi label kelas `actual_paid` tidak sangat timpang (misal 100% unpaid).
3. **Error:** `psycopg2.OperationalError: Connection refused`
   - **Penyebab:** Server database PostgreSQL belum berjalan atau konfigurasi koneksi di `settings.py` salah.
   - **Solusi:** Pastikan service PostgreSQL jalan, periksa string koneksi di `DB_URL` dalam file `settings.py`, dan pastikan *username/password* PostgreSQL yang digunakan valid.
4. **Error:** `ValueError: Terdapat NULL pada recovery_score`
   - **Penyebab:** Model artifact rusak atau ada kolom di `FEATURE_COLS` yang tidak dapat dikonversi ke numerik.
   - **Solusi:** Periksa `config/settings.py` jika ada tambahan fitur baru, pastikan `compute_contract_features` dan metode lainnya hanya menghasilkan tipe *float/integer*, dan *retrain* model.
5. **Error:** `QC hard-fail: duplicate_contract_no`
   - **Penyebab:** Data `contract_snapshot` memiliki baris duplikat untuk `contract_no` yang sama.
   - **Solusi:** Sistem AI membaca kontrak secara unik. Hapus duplikasi data pada tingkat tabel *raw database* `contract_snapshot` agar integrasi relasi satu *contract* = satu baris hasil *score* tetap valid.

---
📝 *Documented for Phase 7 Production Deployment.*
