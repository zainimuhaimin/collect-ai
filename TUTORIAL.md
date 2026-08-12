# Tutorial — Menjalankan CollectAI dari Awal

> Panduan **prosedural, langkah-per-langkah**, dari `git clone` sampai sistem
> berjalan penuh dan siap didemokan (termasuk demo Area 1 performance, Area 2
> day-to-day sync, dan Area 3 AI Reasoning). Untuk referensi arsitektur &
> konsep yang lebih dalam, baca [`README.md`](README.md) — dokumen ini FOKUS
> ke "langkah apa, dalam urutan apa, dan bagaimana memverifikasi setiap
> langkah berhasil" sebelum lanjut ke langkah berikutnya.
>
> Ikuti berurutan dari atas ke bawah kalau ini pertama kalinya Anda
> menjalankan project ini.

---

## 0. Prasyarat

| Software | Versi minimum | Cek dengan |
|---|---|---|
| Python | 3.9+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| PostgreSQL | 14+ | `psql --version` |
| Git | — | `git --version` |

macOS tambahan: `brew install libomp` (dibutuhkan XGBoost).

**Kalau memilih Docker Compose** (lebih cepat, lompat ke §1B): cukup Docker +
Docker Compose, tidak perlu Python/Node/Postgres lokal.

---

## 1A. Setup manual — langkah demi langkah

### 1A.1 Clone & masuk direktori

```bash
git clone <url-repo-anda> collect-ai
cd collect-ai
```

### 1A.2 Virtual environment Python (SATU untuk semua komponen)

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r app/backend/requirements.txt
pip install -r app/machine-learning/requirements.txt
pip install -r faker/requirements.txt
```

**✅ Verifikasi:** `python3 -c "import fastapi, xgboost, pandas"` tidak error.

### 1A.3 File kredensial

```bash
cp .env.example .env
```

Buka `.env`, isi minimal:
- `PGHOST`, `PGPORT` (default `localhost:5432`), `PGUSER`, `PGPASSWORD`, `PGDATABASE`
- `JWT_SECRET` — ganti dari default kalau bukan sekadar demo lokal

Biarkan `AI_REASONING_ENABLED=false` untuk sekarang — akan diaktifkan di §6
kalau Anda ingin mendemokan Area 3.

### 1A.4 Buat database & schema

```bash
createdb collect_ai   # sesuaikan nama dengan PGDATABASE di .env

psql -d collect_ai -f schema.sql
```

**✅ Verifikasi:**
```bash
psql -d collect_ai -c "\dt" | wc -l   # harus menampilkan puluhan tabel
```

### 1A.5 User login

```bash
cd app/backend
python -m scripts.seed_dev_user
cd ../..
```

**✅ Verifikasi:** `psql -d collect_ai -c "SELECT username FROM users;"` menampilkan `admin`.

### 1A.6 Generate data sintetis

```bash
cd faker
python generate-faker-realistic.py --reset --customers 2000
cd ..
```

Ini butuh 1-2 menit untuk 2.000 customer. `--reset` diperlukan karena
generator MENOLAK menulis ke tabel yang sudah berisi data (mencegah
kecelakaan menimpa data produksi).

**✅ Verifikasi:**
```bash
psql -d collect_ai -c "SELECT count(*) FROM customer_master;"   # ~2000
psql -d collect_ai -c "SELECT count(*) FROM contract_snapshot;" # ~2900
```

### 1A.7 Latih model & jalankan scoring pertama

```bash
cd app/machine-learning
python pipelines/train_initial_model.py    # WAJIB pertama — model recovery
python pipelines/train_self_cure.py
python pipelines/train_roll_forward.py
python pipelines/train_ptp_success.py
python pipelines/daily_scoring.py          # menghasilkan ke-4 skor sekaligus
cd ../..
```

Setiap `train_*.py` butuh ~10-30 detik pada 2.000 customer. Kalau salah satu
gagal dengan AUC rendah, itu bisa jadi normal untuk dataset kecil — lanjut
saja, atau baca `app/machine-learning/README.md` §Troubleshooting.

**✅ Verifikasi:**
```bash
ls app/machine-learning/models/          # harus ada *.pkl + registry.json
psql -d collect_ai -c "SELECT count(*) FROM ai_intelligence_output;"  # ~2900
```

### 1A.8 Jalankan backend & frontend

```bash
# Terminal 1
cd app/backend && uvicorn main:app --reload

# Terminal 2
cd app/frontend && npm install && npm run dev
```

**✅ Verifikasi:** buka `http://localhost:5173`, login `admin`/`admin123`,
dashboard menampilkan data (bukan kosong/error). Swagger API di
`http://localhost:8000/docs`.

---

## 1B. Setup cepat — Docker Compose (alternatif §1A)

```bash
cp .env.example .env    # JWT_SECRET boleh default HANYA untuk local dev
docker compose up --build
```

| Layanan | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000/docs |
| Postgres (dari host) | `localhost:5433` |

Compose **belum** menjalankan generator data atau training — begitu
container jalan, lanjutkan dari langkah 1A.6 (generate data) dan 1A.7 (latih
model), TAPI jalankan `python` di dalam venv lokal Anda yang menunjuk ke
`PGPORT=5433` (atau `docker compose exec backend ...` kalau ingin di dalam
container).

---

## 2. Sanity check sebelum lanjut ke demo

```bash
cd app/machine-learning && pytest tests/ -q    # harus: semua PASS
cd ../backend && pytest tests/ -q              # harus: semua PASS (butuh DB nyala)
cd ../..
```

> ⚠️ Test backend menyisipkan & menghapus baris di beberapa tabel governance
> sebagai bagian dari pengujian. Kalau Anda peduli isi tabel
> `model_governance_config`/`model_governance_audit_log`, snapshot dulu
> sebelum menjalankan.

Kalau kedua suite hijau, sistem inti (data → training → scoring → API →
UI) sudah terbukti bekerja end-to-end. Bagian selanjutnya adalah demo
per-Area untuk presentasi.

---

## 3. Demo Area 1 — Performance & Scalability

Tujuan demo: menunjukkan sistem sudah diuji skalanya dan tahu batasnya,
bukan cuma "jalan di laptop saya."

```bash
cd perf

# Sweep skala kecil, aman untuk dijalankan langsung di depan audiens (~5 menit)
python benchmark_scale.py --rungs 5000,10000,25000 \
  --max-stage-seconds 300 --max-rss-gb 14 --min-free-disk-gb 3

# Lihat hasilnya
cat results/scale_sweep.csv
```

⚠️ **`benchmark_scale.py` memanggil `scripts/reset-demo.sh --yes` di setiap
rung** — ini akan MENGHAPUS data yang sedang Anda pakai untuk demo Area 2/3.
**Jalankan Area 1 PALING AWAL** dalam rangkaian demo, atau di database/mesin
terpisah, supaya tidak menghapus setup demo Area 2/3 yang sudah disiapkan.

Untuk angka lengkap yang sudah diukur sebelumnya (100rb-250rb customer, plus
proyeksi ke 5 juta), lihat `performance-report.md` dan bagian Area 1 di
[`bahan-presentasi-area-1-2-3.md`](bahan-presentasi-area-1-2-3.md) — tidak
perlu diukur ulang setiap kali presentasi, kecuali reviewer secara spesifik
minta bukti langsung.

---

## 4. Demo Area 2 — Day-to-Day Sync

Tujuan demo: membuktikan skor AI bergerak seiring waktu, bukan snapshot
statis. Dua cara — pilih sesuai audiens.

### 4a. Versi tampil-di-web (paling meyakinkan, tunjukkan langsung di browser)

```bash
# WAJIB mulai dari DB bersih
./scripts/reset-demo.sh --yes

# Siapkan D0, lalu BERHENTI (supaya bisa dilihat di web dulu)
python scripts/simulate_days.py --dates 2026-09-01 --bootstrap-only \
  --horizon 2026-09-30 --customers 500 --seed 20260101
```

→ Buka web, pilih satu kontrak, catat `recovery_score`/`risk_segment`/
`nba_recommendation`-nya.

```bash
# Majukan tanggal — TANPA reset, TANPA training ulang
python scripts/simulate_days.py --dates 2026-09-30 --continue
```

→ **Refresh halaman kontrak yang sama** — skornya sudah berubah. Bisa
diulang dengan tanggal lain untuk menunjukkan pergerakan bertahap.

### 4b. Versi laporan agregat (untuk angka ringkasan lintas banyak kontrak)

```bash
./scripts/reset-demo.sh --yes
python scripts/simulate_days.py \
  --dates 2026-09-01,2026-09-08,2026-09-30 \
  --customers 500 --seed 20260101
```

Perhatikan output di terminal: bootstrap D0 akan melatih ke-4 model (butuh
waktu paling lama), lalu setiap tanggal berikutnya hanya menjalankan scoring
ulang (jauh lebih cepat, tidak ada training).

```bash
python scripts/movement_report.py --out reports/movement_demo.md --top-n 10
open reports/movement_demo.md
```

**✅ Verifikasi hasil demo layak ditunjukkan:** buka `reports/movement_demo.md`,
pastikan matriks transisi risk_segment **BUKAN 100% diagonal** (kalau
diagonal semua, berarti tidak ada pergerakan nyata — sesuatu salah, jangan
dipresentasikan sampai diperbaiki). Cari contoh "top mover" paling dramatis
di laporan untuk cerita konkret saat presentasi.

Detail metodologi & angka contoh: lihat Area 2 di
[`bahan-presentasi-area-1-2-3.md`](bahan-presentasi-area-1-2-3.md).

---

## 5. Demo Area 3 — AI Reasoning (LLM)

### 5.1 Aktifkan AI Reasoning

Di `.env`:
```
AI_REASONING_ENABLED=true
GOOGLE_AI_STUDIO_API_KEYS=["ISI-API-KEY-GEMINI-ANDA"]
AI_REASONING_DAILY_CALL_LIMIT=300
```

Dapatkan API key dari [Google AI Studio](https://aistudio.google.com/).
Restart backend setelah mengubah `.env`.

### 5.2 Demo lewat UI (paling natural untuk audiens)

1. Buka halaman **Customer Detail** untuk salah satu debitur dengan ≥1
   kontrak aktif.
2. Klik tombol **Generate** pada kartu AI Reasoning.
3. Tunggu beberapa detik — hasil (ringkasan, strategi penanganan,
   rekomendasi NBA per kontrak) muncul di kartu.

⚠️ **Setiap klik "Generate" untuk debitur BARU memicu panggilan berbayar ke
Gemini.** Debitur yang sudah pernah di-generate dengan data yang sama akan
memakai cache (`ai_reasoning_output`), tidak memanggil API lagi. Cek kuota
harian Anda sebelum demo langsung ke banyak debitur berturut-turut.

### 5.3 Demo harness evaluasi (untuk audiens yang lebih teknis)

```bash
# Tier 1/2/3 — deterministic checks + LLM-as-judge + self-consistency
# (Tier 2/GLM butuh judge_api_keys terisi di .env, kalau kosong tier itu dilewati)
python scripts/run_ai_reasoning_eval.py --limit 20 --tier3-sample 5 --tier3-k 3

# Tier 4 — akurasi terhadap kunci jawaban tersembunyi (butuh data faker
# yang di-generate dengan --dump-latents, lihat faker/README.md)
python scripts/evaluate_tier4_oracle.py --out reports/tier4_oracle.md

# Ablasi anchoring rule-NBA (N=50 default, boleh diperkecil untuk demo cepat)
python scripts/ablation_nba.py --n 10 --out reports/ablation_nba_demo.md
```

⚠️ Ketiga script ini memanggil Gemini secara nyata (kecuali Tier 4, yang
murni analisis data lokal) — perhatikan kuota harian sebelum menjalankan
`--limit`/`--n` besar.

Untuk detail metodologi 4-tier, hasil nyata yang sudah diperoleh (termasuk
keterbatasan kuota API), dan naskah presentasi Tier 4 untuk audiens
non-teknis: lihat Area 3 di
[`bahan-presentasi-area-1-2-3.md`](bahan-presentasi-area-1-2-3.md) dan
`ai-reasoning-evaluation.md`.

---

## 6. Selesai demo — reset untuk sesi berikutnya

```bash
./scripts/reset-demo.sh --yes
```

Ini men-TRUNCATE seluruh tabel data (kecuali `users`), menghapus
`app/machine-learning/models/*` dan `registry.json`, dan menghapus
`logs/scoring_log.csv`. Setelah reset, mulai lagi dari §1A.6 (generate data)
kalau ingin sesi demo baru.

---

## Troubleshooting cepat

| Masalah | Solusi |
|---|---|
| `libomp.dylib not found` (macOS) | `brew install libomp` |
| `psycopg2.OperationalError: Connection refused` | Postgres belum jalan, atau `.env` salah host/port. Docker Compose pakai port host `5433`, bukan `5432` |
| `FileNotFoundError: Champion model belum tersedia` | Jalankan `python pipelines/train_initial_model.py`, atau klik **Sync** di UI |
| `RuntimeError: tabel ... sudah berisi data` (faker) | Tambahkan `--reset` |
| Frontend menampilkan data palsu/statis terus | `VITE_ENABLE_MSW=true` aktif — set `false` di env frontend untuk pakai backend asli |
| Login gagal walau kredensial benar | Tabel `users` belum di-seed — `cd app/backend && python -m scripts.seed_dev_user` |
| AI Reasoning error 429 / quota | Kuota harian Gemini habis — tunggu reset harian, atau tambah API key lain di `GOOGLE_AI_STUDIO_API_KEYS` (array, sistem rotasi otomatis) |
| `benchmark_scale.py` menghapus data demo Area 2/3 saya | Memang begitu — jalankan Area 1 (§3) sebelum menyiapkan demo Area 2/3, tidak sesudahnya |

Untuk masalah yang lebih spesifik per komponen, lihat bagian Troubleshooting
di masing-masing README: [`app/backend/README.md`](app/backend/README.md),
[`app/machine-learning/README.md`](app/machine-learning/README.md),
[`faker/README.md`](faker/README.md), [`app/frontend/README.md`](app/frontend/README.md).
