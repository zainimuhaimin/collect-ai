# CollectAI

Sistem *debt collection intelligence* untuk multifinance/leasing: memprediksi
kemungkinan nasabah menunggak akan membayar, merekomendasikan saluran penagihan
terbaik (*Next Best Action*), dan menyusun tawaran restrukturisasi — lengkap
dengan dashboard operasional untuk petugas collection dan supervisor.

Repo ini adalah **monorepo** berisi 5 komponen yang berbagi **satu database
Postgres** dan **satu file `.env` di root**.

---

## Daftar isi

- [Peta komponen](#peta-komponen)
- [Alur data ujung ke ujung](#alur-data-ujung-ke-ujung)
- [Quick start dengan Docker Compose](#quick-start-dengan-docker-compose)
- [Quick start manual](#quick-start-manual)
- [Struktur direktori](#struktur-direktori)
- [Konsep & istilah](#konsep--istilah-yang-wajib-dipahami)
- [Tugas-tugas umum](#tugas-tugas-umum)
- [Testing](#testing)
- [Peta dokumentasi](#peta-dokumentasi)
- [Batasan & catatan penting](#batasan--catatan-penting-yang-diketahui)
- [Troubleshooting](#troubleshooting)

---

## Peta komponen

| Komponen | Isi | README |
|---|---|---|
| `app/backend/` | REST API FastAPI — menyajikan data customer/kontrak/dashboard ke frontend, dan memicu pipeline ML lewat tombol Sync | [baca](app/backend/README.md) |
| `app/frontend/` | SPA React 19 + Vite + Tailwind — 5 menu untuk petugas collection & supervisor | [baca](app/frontend/README.md) |
| `app/machine-learning/` | Pipeline XGBoost: feature engineering, 4 model scoring, MLOps (drift/retrain), batch restrukturisasi | [baca](app/machine-learning/README.md) |
| `app/shared/` | `restructuring_offer_calculator.py` — kalkulasi tawaran restrukturisasi. **Satu-satunya salinan**, di-import bersama oleh backend dan ML | — |
| `app/core-banking/` | Simulator origination kontrak. Sistem **terpisah** secara sengaja: hanya modul ini yang boleh membuat kontrak baru | — |
| `faker/` | Generator data sintetis realistis + validator kebocoran data (*leakage*) | [baca](faker/README.md) |

Prinsip pemisahan yang dipegang di repo ini:

- **Backend tidak menghitung logika bisnis restrukturisasi.** Semuanya di
  `app/shared/`, supaya batch ML dan API on-demand tidak bisa memberi angka
  berbeda untuk kontrak yang sama.
- **Backend dan ML tidak membuat kontrak baru.** Backend hanya mencatat
  keputusan nasabah (`offer_status='ACCEPTED'`); `app/core-banking/originator.py`
  yang mengeksekusinya menjadi kontrak baru.
- **Satu Postgres, satu `.env`.** Tidak ada mock/in-memory repository di
  backend — semua endpoint membaca database asli yang sama dipakai pipeline ML.

---

## Alur data ujung ke ujung

```
                       ┌──────────────────────────────┐
                       │  faker/  (data sintetis)      │
                       │  atau data core banking asli  │
                       └───────────────┬───────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │           4 TABEL INPUT             │
                    │  customer_master                    │
                    │  contract_snapshot                  │
                    │  payment_history                    │
                    │  lkp_interaction                    │
                    └──────────────────┬──────────────────┘
                                       │
        ┌──────────────────────────────▼──────────────────────────────┐
        │  app/machine-learning/                                       │
        │                                                              │
        │  feature_engineering.py ──► 36 fitur kontrak+customer        │
        │            │                                                 │
        │            ├──► 4 model XGBoost (recovery / self_cure /       │
        │            │    roll_forward / ptp_success)                   │
        │            ├──► business_rules.py (risk segment, NBA,         │
        │            │    priority)                                     │
        │            └──► cbs_builder.py (profil perilaku customer)     │
        └──────────────────┬───────────────────────┬───────────────────┘
                           │                       │
              ┌────────────▼───────────┐ ┌─────────▼──────────────────┐
              │ ai_intelligence_output │ │ customer_behavioral_standing│
              │ (skor harian/kontrak)  │ │ (CBS — grade, sensitivity)   │
              └────────────┬───────────┘ └─────────┬──────────────────┘
                           │                       │
                           └───────────┬───────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │ restructuring_runner.py + app/shared/            │
              │ ──► restructuring_recommendation_output          │
              └────────────────────────┬────────────────────────┘
                                       │
              ┌────────────────────────▼────────────────────────┐
              │  app/backend/  (FastAPI, port 8000)              │
              │  Router → Service → Repository (interface)        │
              └────────────────────────┬────────────────────────┘
                                       │  JSON (snake_case)
              ┌────────────────────────▼────────────────────────┐
              │  app/frontend/  (React, port 5173)               │
              │  Zod validasi → camelCase → React Query → pages  │
              └─────────────────────────────────────────────────┘
```

**Arah dependency-nya satu arah.** Frontend tidak pernah menyentuh database;
backend tidak pernah meng-import modul ML ke dalam prosesnya (Sync memanggil
pipeline lewat *subprocess*).

---

## Quick start dengan Docker Compose

Cara **tercepat** menjalankan seluruh stack. Schema database dibuat otomatis saat
volume Postgres pertama kali dibuat.

```bash
# 1. Siapkan .env di root (dipakai bersama semua komponen)
cp .env.example .env
#    Untuk Docker Compose, PGPASSWORD boleh dibiarkan default; JWT_SECRET
#    WAJIB diganti kalau bukan di local dev.

# 2. Jalankan
docker compose up --build
```

| Layanan | URL / port | Catatan |
|---|---|---|
| Frontend | http://localhost:5173 | Vite dev server, hot reload |
| Backend | http://localhost:8000 | Swagger di `/docs`, ReDoc di `/redoc` |
| Postgres | `localhost:5433` | Sengaja **5433** di host supaya tidak bentrok dengan Postgres lokal di 5432 |

Beberapa hal yang perlu diketahui soal compose:

- `PGHOST`/`PGPORT` **tidak** dibaca dari `.env` untuk container backend — di
  dalam jaringan compose, backend harus menghubungi Postgres lewat nama service
  `db`, bukan `localhost`.
- Frontend di compose menyala dengan `VITE_ENABLE_MSW="true"` (mock API MSW).
  Untuk memakai backend sungguhan, set `false`.
- Compose belum menjalankan generator data maupun training. Setelah `up`,
  lanjutkan dengan [seed data & model pertama](#3-seed-data--model-pertama).

---

## Quick start manual

Untuk development sehari-hari. Prasyarat: **Python 3.9+**, **Node 20+** (Node 24 dipakai di compose),
**PostgreSQL 14+**. Pengguna macOS juga butuh `brew install libomp` untuk
XGBoost.

### 1. Environment & dependency

```bash
# Satu venv untuk SELURUH komponen Python (backend, ML, faker, core-banking)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r app/backend/requirements.txt
pip install -r app/machine-learning/requirements.txt
pip install -r faker/requirements.txt

# Kredensial bersama
cp .env.example .env               # lalu isi nilai asli
```

### 2. Database

```bash
createdb collect_ai   # kalau belum ada

# Schema gabungan: 4 tabel input + tabel output ML + tabel restrukturisasi
psql -d collect_ai -f app/machine-learning/config/schema_combined.sql

# Tabel khusus backend: users + governance/audit
psql -d collect_ai -f app/backend/db/schema_users.sql
psql -d collect_ai -f app/backend/db/schema_governance.sql

# User dev untuk login (admin / admin123)
cd app/backend && python -m scripts.seed_dev_user && cd ../..
```

Semua file schema bersifat **idempoten** (`CREATE TABLE IF NOT EXISTS` /
`ADD COLUMN IF NOT EXISTS`), jadi aman dijalankan berulang. Repo ini **tidak
memakai migration framework** — penambahan kolom dilakukan dengan menambah
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` ke file schema, lalu `psql -f` lagi.

### 3. Seed data & model pertama

```bash
# Data sintetis: 2000 customer (~2900 kontrak) — lihat faker/README.md
cd faker && python generate-faker-realistic.py --reset && cd ..
```

Model bisa dilatih dengan **dua cara** — pilih salah satu:

**A. Lewat tombol Sync di UI (paling mendekati alur nyata).** Jalankan backend
dan frontend, login, buka halaman **AI Intelligence**, klik **Sync**. Backend
akan melatih keempat model yang belum punya champion, lalu scoring, lalu
monitoring — semuanya di background thread, statusnya bisa di-poll.

**B. Lewat CLI.**

```bash
cd app/machine-learning
python pipelines/train_initial_model.py    # model recovery (champion wajib ada)
python pipelines/train_self_cure.py
python pipelines/train_roll_forward.py
python pipelines/train_ptp_success.py
python pipelines/daily_scoring.py          # menghasilkan ke-4 skor sekaligus
python pipelines/weekly_mlops.py           # drift + monitoring (opsional)
cd ../..
```

> Direktori `app/machine-learning/models/` **belum ada** di repo bersih — ia
> dibuat saat training pertama, bersama `registry.json`. Jadi kalau baru
> clone, wajar kalau folder itu tidak terlihat.

### 4. Jalankan aplikasi

```bash
# Terminal 1 — backend
cd app/backend && uvicorn main:app --reload      # http://localhost:8000

# Terminal 2 — frontend
cd app/frontend && npm install && npm run dev    # http://localhost:5173
```

Dev server Vite memproksikan `/api` → `http://localhost:8000/api/v1`, jadi
frontend tidak perlu tahu prefix versi API. Login: `admin` / `admin123`.

---

## Struktur direktori

```text
collect-ai/
├── README.md                     # ← dokumen ini
├── .env.example                  # template kredensial bersama (copy jadi .env)
├── docker-compose.yml            # db + backend + frontend
├── init_table.sql                # DDL 4 tabel input versi paling awal (historis;
│                                 #   pemakaian sekarang: schema_combined.sql)
├── *.md                          # dokumen desain per fitur — lihat "Peta dokumentasi"
│
├── app/
│   ├── backend/                  # FastAPI — Router → Service → Repository
│   │   ├── main.py               #   entry point + health check di GET "/"
│   │   ├── core/                 #   config (pydantic-settings) + DI wiring
│   │   ├── domain/               #   dataclass murni, bebas Pydantic/FastAPI
│   │   ├── schemas/              #   Pydantic — boundary HTTP saja
│   │   ├── repositories/         #   interfaces.py + implementasi Postgres
│   │   ├── services/             #   business logic, depend ke interface saja
│   │   ├── api/v1/routers/       #   auth, customers, contracts, dashboard,
│   │   │                         #   restructuring, restructuring_groups,
│   │   │                         #   ai_intelligence
│   │   ├── db/                   #   schema_users.sql, schema_governance.sql
│   │   ├── scripts/              #   seed_dev_user.py
│   │   └── tests/                #   test_smoke.py (E2E ke Postgres asli)
│   │
│   ├── frontend/                 # React 19 + Vite + Tailwind (MD3 tokens)
│   │   ├── src/api/              #   ky client, Zod wrapper, query keys
│   │   ├── src/domains/          #   per domain: .api.ts + .schema.ts + hooks
│   │   ├── src/pages/            #   10 halaman
│   │   ├── src/mocks/            #   MSW handlers + fixtures
│   │   └── docs/api/             #   kontrak HTTP per modul
│   │
│   ├── machine-learning/
│   │   ├── config/               #   settings.py + schema*.sql
│   │   ├── src/                  #   feature engineering, scoring, rules, MLOps
│   │   ├── pipelines/            #   4 train_*, daily_scoring, weekly_mlops,
│   │   │                         #   restructuring_runner
│   │   ├── models/               #   artifact + registry.json (dibuat saat training)
│   │   └── tests/                #   6 modul pytest
│   │
│   ├── shared/
│   │   └── restructuring_offer_calculator.py   # SATU salinan, dipakai BE + ML
│   │
│   └── core-banking/
│       └── originator.py         # eksekusi offer ACCEPTED jadi kontrak baru
│
└── faker/
    ├── generate-faker-realistic.py   # generator utama (pakai ini)
    ├── validate_leakage.py           # audit kebocoran data & realisme
    ├── generate-dataset.py           # generator lama (deprecated)
    └── helpers/database.py           # loader Postgres, idempoten
```

---

## Konsep & istilah yang wajib dipahami

| Istilah | Arti |
|---|---|
| **DPD** | *Days Past Due* — jumlah hari keterlambatan angsuran tertua yang belum dibayar |
| **OTS** | *Outstanding* — sisa kewajiban. `prnc_ots` = pokok, `intr_ots` = bunga belum jatuh tempo. `total_ots` = keduanya (**bruto**) |
| **Cycle / bucket** | Pengelompokan DPD: C0 (1-30), C1 (31-60), C2 (61-90), C3+ (>90). `dpd=0` di luar semua bucket |
| **PTP** | *Promise To Pay* — janji bayar dari nasabah. Statusnya `OPEN` (belum jatuh tempo), `KEPT`, atau `BROKEN` |
| **LKP** | Log interaksi penagihan (satu baris per upaya kontak) |
| **AMBC** | *Amount Billed Current* — nominal yang ditagihkan pada siklus berjalan |
| **NBA** | *Next Best Action* — channel penagihan yang direkomendasikan. Domainnya **tepat 5 nilai**: `WA`, `Deskcoll`, `Visit`, `Somasi`, `Pickup` |
| **Risk segment** | **Tepat 4 nilai**: `Won't Pay`, `Cannot Pay`, `Self-cure`, `Can Pay` |
| **CBS** | *Customer Behavioral Standing* — profil perilaku level customer (grade A-D, sensitivitas channel, B-list) |
| **Champion / Challenger** | Model yang dipakai produksi vs kandidat penggantinya yang dievaluasi *shadow mode* |
| **Label window** | 30 hari (`LABEL_WINDOW_DAYS`). Semua model memakai satu label: `actual_paid` — ada pembayaran `Full`/`Partial` dalam 30 hari setelah tanggal referensi |
| **Feature cutoff** | Fitur hanya boleh memakai data s/d `reference_date − 30 hari`. Ini penjaga anti-*leakage* utama — jangan dilemahkan |

### Empat model, satu label

| Model | Fitur | Peran |
|---|---|---|
| `recovery` | 36 | Skor utama. **Wajib** ada championnya, kalau tidak `daily_scoring` gagal |
| `self_cure` | 12 | Kemungkinan pulih sendiri tanpa intervensi |
| `roll_forward` | 14 | Risiko naik ke bucket DPD berikutnya. **Nilai tersimpan sudah dibalik** = P(tidak bayar) |
| `ptp_success` | 11 | Kemungkinan janji bayar ditepati |

Ketiga model selain `recovery` bersifat *soft-degrade*: kalau artifact-nya tidak
ada, kolomnya `NULL` dan scoring tetap jalan.

---

## Tugas-tugas umum

```bash
# Regenerasi ulang seluruh data sintetis (menghapus data lama + tabel derivatif)
cd faker && python generate-faker-realistic.py --reset

# Audit kebocoran data & realisme generator
cd faker && python validate_leakage.py

# Scoring ulang tanpa training ulang
cd app/machine-learning && python pipelines/daily_scoring.py

# Regenerasi tawaran restrukturisasi saja
cd app/machine-learning && python pipelines/restructuring_runner.py

# Lihat kontrak OpenAPI tanpa menjalankan frontend
open http://localhost:8000/docs

# Frontend tanpa backend (pakai mock MSW)
cd app/frontend && VITE_ENABLE_MSW=true npm run dev
```

### Mengubah aturan bisnis

Hampir semua threshold ada di **satu** tempat: `app/machine-learning/config/settings.py`.
Ubah nilainya, jalankan `daily_scoring.py` lagi — tidak perlu menyentuh kode
inti. Pengecualian: mengubah `FEATURE_COLS` atau `TARGET_COL` **mewajibkan**
training ulang.

Bobot CBS bisa diubah tanpa deploy, lewat UI halaman AI Intelligence (tersimpan
di tabel `model_governance_config`, dengan audit trail).

---

## Testing

```bash
# Backend — E2E lewat TestClient ke Postgres asli (56 test)
cd app/backend && pytest tests/ -q

# Machine learning — unit test murni, tidak butuh DB (155 test)
cd app/machine-learning && pytest tests/ -q

# Frontend — lint saja; belum ada test runner
cd app/frontend && npm run lint
```

> **Peringatan:** `app/backend/pytest` berjalan terhadap **database dev asli**,
> bukan mock. Test yang butuh skenario spesifik menyisipkan baris throwaway dan
> membersihkannya sendiri, **tapi** suite ini diketahui meninggalkan dua jejak:
> deskripsi `model_governance_config.cbs_weights` tertimpa, dan satu baris
> `model_governance_audit_log` dengan `performed_by='test.smoke.governance'`.
> Kalau Anda peduli pada isi tabel itu, snapshot dulu sebelum menjalankan test.

---

## Peta dokumentasi

Dokumen desain per fitur ada di root. Statusnya beragam — beberapa sudah
diimplementasikan, beberapa masih rencana:

| Dokumen | Isi | Status |
|---|---|---|
| [`flow-and-rules.md`](flow-and-rules.md) | Alur bisnis & aturan penagihan | Referensi |
| [`scoring-engine.md`](scoring-engine.md) | Desain mesin scoring & fitur | Terimplementasi |
| [`ml-ops-pipeline.md`](ml-ops-pipeline.md) | Drift, retrain, champion/challenger | Terimplementasi |
| [`restructuring-engine-tasks.md`](restructuring-engine-tasks.md) | Engine restrukturisasi | Terimplementasi |
| [`backend-architecture-tasks.md`](backend-architecture-tasks.md) | Arsitektur berlapis backend | Terimplementasi |
| [`frontend-layout-upgrade-tasks.md`](frontend-layout-upgrade-tasks.md) | 5 menu, TASK-A s/d TASK-F | Sebagian terimplementasi |
| [`frontend-refinement-round2-tasks.md`](frontend-refinement-round2-tasks.md) · [`round4`](frontend-refinement-round4-tasks.md) | Perbaikan UI bertahap | Terimplementasi |
| [`ai-reasoning-api-upgrade-tasks.md`](ai-reasoning-api-upgrade-tasks.md) | Integrasi LLM untuk narasi analisa | **Rencana** — belum ada kode |
| [`collect-ai-upgrade.md`](collect-ai-upgrade.md) · [`collection-task.md`](collection-task.md) · [`collection-handoff.md`](collection-handoff.md) | Catatan historis & handoff | Historis |

Dokumentasi kontrak HTTP per modul: [`app/frontend/docs/api/`](app/frontend/docs/api/README.md).

---

## Batasan & catatan penting yang diketahui

Didaftar terbuka supaya tidak ditemukan ulang dengan susah payah:

1. **Endpoint `/customers` dan `/contracts` belum punya autentikasi.** Tidak ada
   dependency auth global di `main.py`. Hanya beberapa route AI Intelligence dan
   Restructuring Approval yang memakai `Depends(get_current_user)`, dan itu pun
   didokumentasikan sebagai *audit trail*, **bukan** gate akses.
2. **Tidak ada RBAC.** Semua menu terlihat oleh setiap user yang login,
   termasuk Restructuring Approval dan AI Intelligence.
3. **AUC "live" di kartu Model Health baru terisi setelah ~30 hari** riwayat
   scoring — angka itu membandingkan skor lampau dengan pembayaran nyata
   sesudahnya, jadi wajar `NULL` di instalasi baru. Yang muncul di
   `registry.json` adalah AUC *cross-validation* saat training, bukan performa live.
4. **`QC_*_PCT` bersifat soft-fail secara default** (`COLLECTAI_STRICT_QC=false`).
   Batas distribusi segmen itu asumsi komposisi portfolio, bukan invariant
   kebenaran pipeline — menggagalkan seluruh run karena komposisi bergeser berarti
   nol skor tersimpan. Pelanggaran tetap dicetak sebagai warning.
5. **Beberapa fitur ML selalu bernilai 0**: `delay_trend`,
   `historical_default_count`, `income_debt_ratio`, `broken_ptp_count` —
   `cbs_builder.build_cbs()` tidak pernah mengembalikannya. `restructure_count`
   juga selalu 0 karena `update_cbs()` tidak punya pemanggil produksi.
6. **`SMS` hilang dari dua peta ranking channel** (`feature_engineering.py` dan
   `business_rules.py`) padahal SMS channel nyata — akibatnya override
   `collection_sensitivity` mati diam-diam untuk nasabah yang paling responsif
   via SMS.
7. **Hyperparameter XGBoost (`n_estimators=500, max_depth=6`) over-parameterized**
   untuk ~2.900 baris data.
8. **Dark mode ditulis tapi belum bisa diaktifkan** — ~373 utility `dark:`
   tersebar di frontend, tapi tidak ada kode yang menambahkan class `dark`.
9. **Frontend belum punya test runner.** Hanya `oxlint`.
10. **`contract_snapshot` tidak punya `snapshot_date`**, jadi ia selalu
    "as-of-hari-ini". Generator data mengompensasi ini dengan membangun snapshot
    pada posisi *feature cutoff* — lihat [`faker/README.md`](faker/README.md).

---

## Troubleshooting

**`xgboost.core.XGBoostError: libomp.dylib not found` (macOS)**
→ `brew install libomp`.

**`psycopg2.OperationalError: Connection refused`**
→ Postgres belum jalan, atau `.env` menunjuk host/port yang salah. Ingat: dengan
Docker Compose, port di **host** adalah `5433`, bukan 5432.

**`FileNotFoundError: Champion model belum tersedia`**
→ Model `recovery` belum pernah dilatih. Jalankan
`python pipelines/train_initial_model.py`, atau klik Sync di UI.

**`RuntimeError: tabel ... sudah berisi data`** saat menjalankan faker
→ Generator menolak menimpa data secara diam-diam. Pakai `--reset` kalau memang
ingin mengganti seluruh dataset.

**Frontend menampilkan "server returned data in an unexpected format"**
→ Response backend tidak lolos validasi Zod. Cek tab Network untuk bentuk
sesungguhnya, lalu bandingkan dengan `src/domains/<modul>/<modul>.schema.ts`.

**Frontend jalan tapi semua data terlihat palsu/statis**
→ `VITE_ENABLE_MSW=true` sedang aktif (default di Docker Compose). Set `false`
untuk memakai backend sungguhan.

**Login gagal walau kredensial benar**
→ Tabel `users` belum di-seed. Jalankan
`cd app/backend && python -m scripts.seed_dev_user`.
