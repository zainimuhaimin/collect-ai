# CollectAI Backend

Backend FastAPI yang menyajikan data customer/kontrak dan opsi restrukturisasi
kredit. Sumber datanya adalah **Postgres yang sama** dipakai pipeline
`app/machine-learning/` — tidak ada mock/in-memory repository, semua endpoint
membaca/menulis ke database asli.

Untuk gambaran keseluruhan sistem (alur data ujung ke ujung, Docker Compose,
istilah domain), baca [README root](../../README.md) lebih dulu.

> ⚠️ **Belum ada autentikasi pada mayoritas endpoint.** Tidak ada dependency auth
> global di `main.py` maupun `api/v1/api.py`. Seluruh route `/customers` dan
> `/contracts` terbuka. `Depends(get_current_user)` hanya dipakai di beberapa
> route AI Intelligence dan Restructuring Approval, dan di sana pun perannya
> **audit trail**, bukan gate akses. Lihat [Batasan yang diketahui](#batasan-yang-diketahui).

## Arsitektur

Satu arah dependency: **Router → Service → Repository (interface)**.

```
app/backend/
├── main.py                        # entry point FastAPI + metadata OpenAPI
├── core/
│   ├── config.py                  # Settings (baca .env di root repo)
│   └── dependencies.py            # SATU-SATUNYA tempat wiring repo konkret
├── domain/models.py                # dataclass murni, TIDAK bergantung Pydantic/FastAPI
├── schemas/                        # Pydantic request/response (boundary HTTP)
├── repositories/
│   ├── interfaces.py               # ICustomerRepository, IContractRepository,
│   │                                # IDashboardRepository, IRestructuringOfferRepository,
│   │                                # IGovernanceConfigRepository, IAiIntelligenceSyncRepository
│   ├── customer_repository.py      # implementasi Postgres
│   ├── contract_repository.py      # implementasi Postgres
│   ├── restructuring_offer_repository.py  # implementasi Postgres
│   ├── dashboard_repository.py      # implementasi Postgres (TASK-B)
│   ├── governance_repository.py     # implementasi Postgres (TASK-F fase 1)
│   └── ai_intelligence_sync_repository.py  # implementasi Postgres (last_scored_at saja)
├── services/                       # business logic, depend ke interface saja
│   └── ai_intelligence_sync_service.py  # job Sync (training-if-missing + scoring), state
│                                          # in-memory module-level singleton (lihat isi file)
├── api/v1/routers/                 # auth, customers, contracts, restructuring,
│                                     # restructuring_groups, dashboard, ai_intelligence
│                                     # (health check ada langsung di main.py, GET "/")
├── db/
│   ├── schema_users.sql             # tabel `users` (login/identity)
│   └── schema_governance.sql        # tabel governance baru (TASK-E/TASK-F)
└── tests/test_smoke.py             # end-to-end lewat TestClient, DB asli
```

Kalkulasi restrukturisasi (haircut, NPV, guardrail, dst) **tidak ada di
backend ini** — itu murni ada di `app/shared/restructuring_offer_calculator.py`,
dipakai bersama oleh backend dan pipeline ML lewat `RestructuringService`. Satu
salinan saja, supaya batch ML dan API on-demand tidak bisa memberi angka berbeda
untuk kontrak yang sama.

Backend juga **tidak pernah membuat kontrak baru**. Ia hanya mencatat keputusan
nasabah (`offer_status='ACCEPTED'`); yang mengeksekusinya menjadi kontrak baru
adalah `app/core-banking/originator.py` — sistem terpisah, disengaja.

## Quick Start

```bash
# 1. Install dependencies (dari root repo, venv yang sama dipakai app/machine-learning/ —
#    Python 3.9, kompatibel dengan seluruh backend ini, tidak butuh venv/versi terpisah)
cd ../..
source .venv/bin/activate  # Windows: .venv\Scripts\activate
cd app/backend
pip install -r requirements.txt

# 2. Pastikan .env ada di ROOT repo (bukan di app/backend/) — lihat .env.example
#    Kredensial ini dipakai bersama oleh backend, machine-learning, dan core-banking.
cat ../../.env.example   # copy jadi ../../.env kalau belum ada, isi kredensial asli

# 3. Buat tabel `users` + tabel governance baru (sekali saja, idempotent) + seed 1 dev user
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f db/schema_users.sql
psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f db/schema_governance.sql   # model_governance_config,
                                                                         # model_governance_audit_log,
                                                                         # restructuring_approval_log
python -m scripts.seed_dev_user   # -> admin / admin123 (dev-only, lihat scripts/seed_dev_user.py)

# 4. Jalankan server
uvicorn main:app --reload
```

Server jalan di `http://localhost:8000`.

## Dokumentasi API (Swagger / ReDoc)

- **Swagger UI (interaktif, bisa langsung test manual)**: http://localhost:8000/docs
- **ReDoc (lebih enak dibaca, read-only)**: http://localhost:8000/redoc
- **OpenAPI JSON mentah**: http://localhost:8000/openapi.json

Swagger UI punya tombol **"Try it out"** di tiap endpoint — isi parameter,
klik Execute, langsung lihat response asli dari database. Semua endpoint
sudah dilengkapi contoh request/response, jadi tidak perlu menebak format.

## Endpoint & Contoh Manual Test (curl)

### 1. Health check

```bash
curl http://localhost:8000/
```

Di root (`/`), BUKAN di bawah `/api/v1` — ini urusan infra (cek proses hidup),
bukan bagian dari API versi tertentu. Response: `{"service": "...", "status":
"ok", "version": "..."}`.

### 2. Daftar Customer (filter chip + search + paginasi)

```bash
curl "http://localhost:8000/api/v1/customers?filter=dpd_30_plus&page=1&page_size=20"
```

`filter` (single-select, default `all`): `all` | `dpd_30_plus` | `high_priority` |
`broken_ptp` | `high_ambc`. `search` — substring match ke `cust_id`. Response:
`{"customers": [...], "page_info": {...}}`, tiap item:

```json
{
  "cust_id": "CUST-00029",
  "name": "Indah Anggriawan",
  "active_contract_count": 2,
  "behavioral_grade": "B",
  "b_list_status": "N",
  "priority": "High"
}
```

`priority` level-Customer: MAX() di antara SEMUA kontrak AKTIF (belum
`closed_via_restructure`) milik customer ini (Critical > High > Medium),
BUKAN dari 1 kontrak yang dipilih arbitrer. `high_priority` — customer punya
>=1 kontrak aktif berprioritas High/Critical (EXISTS, konsisten dengan
definisi di atas).

### 3. Detail 360° satu customer

```bash
curl http://localhost:8000/api/v1/customers/CUST-00029
```

Join `customer_master` + `customer_behavioral_standing` + kontrak utama +
skor `ai_intelligence_output` kontrak itu. `risk_segment` apa adanya dari DB
(`Cannot Pay`/`Self-cure`/`Won't Pay`/`Can Pay`), TIDAK diterjemahkan.

### 4. Daftar kontrak milik 1 customer

```bash
curl http://localhost:8000/api/v1/customers/CUST-00029/contracts
```

List kosong VALID kalau customer ada tapi belum punya kontrak — `404` hanya
kalau `cust_id` sama sekali tidak ada di `customer_master`.

### 5. Daftar Contract (filter chip + search + paginasi)

```bash
curl "http://localhost:8000/api/v1/contracts?filter=high_priority&page=1&page_size=20"
```

Sama seperti daftar Customer tapi murni per-baris. `search` — substring match
ke `contract_no` ATAU `cust_id`.

### 6. Detail penuh 1 kontrak

```bash
curl http://localhost:8000/api/v1/contracts/CTR-00029-1
```

7 bagian dalam 1 payload: ringkasan, rincian outstanding (`principal`/`interest`/`total`),
AI scoring, riwayat pembayaran (12 terakhir), status restrukturisasi (read-only).
`404` kalau `contract_no` tidak ditemukan.

### 7. Timeline aktivitas kontrak

```bash
curl http://localhost:8000/api/v1/contracts/CTR-00029-1/activity-log
```

Endpoint yang SAMA dipakai Contract Detail (timeline penuh) dan expand
per-kontrak di Customer Detail — 1 sumber kebenaran untuk log aktivitas.

### 8. Ringkasan Dashboard

```bash
curl http://localhost:8000/api/v1/dashboard/summary
```

KPI + DPD buckets + contactability funnel/channel efficiency + restructuring
pipeline snapshot + risk segment distribution + sync note — semua dihitung
langsung dari tabel yang sama dipakai `app/machine-learning/`.

### 9. Opsi restrukturisasi (on-demand)

```bash
curl http://localhost:8000/api/v1/customers/CUST-00029/restructuring-options
```

Perhatikan `eligibility_tier` di response:
- `AUTO` — `offers` boleh langsung ditawarkan
- `MANUAL_REVIEW` — `offers` tetap terisi, tapi tunggu approval supervisor
- `BLOCKED` — `offers` selalu kosong (data kontrak tidak valid)

**`offers` juga bisa kosong walau tier-nya bukan `BLOCKED`** — itu artinya
tawaran yang terhitung tidak lolos guardrail. Guardrail sekarang menguji **dua
sisi**: sisi lender (NPV risk-adjusted membaik) dan sisi nasabah (cicilan baru
wajib turun minimal `MIN_INSTALLMENT_REDUCTION_PCT`, total bayar tidak boleh
melebihi `MAX_TOTAL_REPAYMENT_RATIO`). Tawaran yang tidak berupa keringanan nyata
**tidak ditampilkan** — lebih baik tidak ada tawaran daripada tawaran yang pasti
ditolak. Alasan penolakannya ada di `rejection_reasons`.

Angka risk-adjusted yang ditampilkan memakai asumsi kenaikan peluang bayar
pasca-restrukturisasi (`restructure_recovery_uplift_pct`) — asumsi yang sama
dipakai batch ML, dibaca dari satu fungsi bersama supaya UI tidak menampilkan
angka yang bertentangan dengan yang meloloskan tawaran itu.

### 10. Customer merespons tawaran (accept/reject)

Ambil dulu `restructure_group_id` yang statusnya `OFFERED` (dari batch harian
ML atau dari `restructuring_recommendation_output` langsung), lalu:

```bash
curl -X POST \
  http://localhost:8000/api/v1/customers/CUST-00029/restructuring-options/RG-CUST-00029-2026-07-21-1/customer-response \
  -H "Content-Type: application/json" \
  -d '{"response": "ACCEPTED"}'
```

Kalau ACCEPTED, jalankan `app/core-banking/originator.py` untuk mengeksekusi
kontrak barunya (backend ini TIDAK membuat kontrak baru sendiri).

Response error yang mungkin muncul:
| Status | Kondisi |
|---|---|
| 403 | `restructure_group_id` bukan milik `cust_id` yang diminta |
| 404 | `cust_id` atau `restructure_group_id` tidak ditemukan |
| 409 | Tawaran masih `GENERATED` (belum di-approve) atau sudah pernah direspons |
| 410 | Tawaran sudah lewat `expiry_date` |

### 11. Restructuring Approval — queue + approve/reject

```bash
# Queue default (GENERATED)
curl http://localhost:8000/api/v1/restructuring-groups

# Histori (comma-separated)
curl "http://localhost:8000/api/v1/restructuring-groups?status=OFFERED,REJECTED"

# Search — substring match ke restructure_group_id ATAU cust_id
curl "http://localhost:8000/api/v1/restructuring-groups?search=CUST-00029"

# Detail 1 grup (bentuk sama dengan 1 item di list) — 404 kalau tidak ditemukan
curl http://localhost:8000/api/v1/restructuring-groups/RG-CUST-00029-2026-07-21-1

# Approve (butuh login — HANYA untuk audit trail, TIDAK ADA gate role, lihat TASK-A)
curl -X POST http://localhost:8000/api/v1/restructuring-groups/RG-CUST-00029-2026-07-21-1/approve \
  -H "Authorization: Bearer $TOKEN"

# Reject — tanpa body/alasan wajib
curl -X POST http://localhost:8000/api/v1/restructuring-groups/RG-CUST-00029-2026-07-21-1/reject \
  -H "Authorization: Bearer $TOKEN"
```

Approve/reject mencatat 1 baris `restructuring_approval_log` (siapa + kapan).
`404` kalau group tidak ditemukan, `409` kalau statusnya bukan `GENERATED` lagi.

### 12. AI Intelligence — Bobot CBS (fase 1)

```bash
# Bobot CBS + Model Health gabungan
curl http://localhost:8000/api/v1/ai-intelligence/model-config

# Simpan bobot baru — sum(weight) HARUS 100 (toleransi ±0.01), else 400
curl -X PUT http://localhost:8000/api/v1/ai-intelligence/weighting-parameters \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '[
    {"label": "WEIGHT_PAYMENT_RATE", "weight": 30, "description": "..."},
    {"label": "WEIGHT_PTP_RELIABILITY", "weight": 25, "description": "..."},
    {"label": "WEIGHT_INTERACTION", "weight": 20, "description": "..."},
    {"label": "WEIGHT_DELAY_SCORE", "weight": 25, "description": "..."}
  ]'

# Audit log semua perubahan config di atas
curl http://localhost:8000/api/v1/ai-intelligence/operational-log
```

Risk & Sub-model Threshold serta Restructuring Policy SENGAJA tidak ada di
sini — di luar scope fase ini (lihat `frontend-layout-upgrade-tasks.md` TASK-F).
`ai_reasoning` di `model_health` masih placeholder (`available: false`) —
`ai_reasoning_output` belum dibangun (`ai-reasoning-api-upgrade-tasks.md`,
task terpisah, belum digarap).

### 13. AI Intelligence — Sync (training-if-missing + scoring)

Tombol "Sync" di halaman AI Intelligence. Urutan langkahnya:

1. Untuk tiap model type (`recovery`/`self_cure`/`roll_forward`/`ptp_success`)
   yang **belum punya champion** (dicek dari
   `app/machine-learning/models/registry.json`) — latih dulu lewat subprocess
   `pipelines/train_*.py`.
2. `pipelines/daily_scoring.py` — 1x saja, menghasilkan ke-4 skor sekaligus.
3. `pipelines/weekly_mlops.py` — **selalu dijalankan**, bukan hanya saat training
   dari nol. Script inilah satu-satunya penulis `model_monitoring_log` (sumber
   kartu "Scoring Model Health" + hitungan drift). Drift dihitung dari hasil
   scoring, jadi harus mengikuti setiap scoring baru; kalau langkah ini
   dilewatkan, kartu health beku di angka run pertama.

Berjalan di background thread — endpoint langsung `202`, poll status-nya.

Tiap job yang selesai/gagal mencatat 1 baris `model_governance_audit_log`
(`action='MODEL_SYNC'`, `performed_by='system (sync)'`, status sebenarnya di
dalam `detail`), sehingga aktivitas Sync muncul di Operational Log. State
in-memory tidak cukup untuk ini karena hilang setiap backend restart.

```bash
# Mulai sync (butuh login — HANYA untuk syarat "logged-in user", tidak ada gate role)
curl -X POST http://localhost:8000/api/v1/ai-intelligence/sync \
  -H "Authorization: Bearer $TOKEN"
# -> 202 {"job_id": "...", "status": "running"}
# -> 409 kalau ada sync lain yang masih berjalan

# Poll status (tidak butuh login)
curl http://localhost:8000/api/v1/ai-intelligence/sync/status
```

```json
{
  "status": "running",
  "started_at": "2026-07-27T10:00:00",
  "finished_at": null,
  "steps": [
    {"model_type": "recovery", "action": "train_then_score", "status": "done"},
    {"model_type": "self_cure", "action": "train_then_score", "status": "running"},
    {"model_type": "roll_forward", "action": "train_then_score", "status": "pending"},
    {"model_type": "ptp_success", "action": "train_then_score", "status": "pending"},
    {"model_type": "daily_scoring", "action": "score", "status": "pending"},
    {"model_type": "weekly_mlops", "action": "weekly_monitoring", "status": "pending"}
  ],
  "last_scored_at": "2026-07-26T23:10:04",
  "error": null
}
```

`last_scored_at` (`MAX(updated_at)` di `ai_intelligence_output`) dihitung
REAL-TIME tiap panggilan GET, independen dari status job — tetap terisi
walau belum pernah ada sync yang jalan lewat endpoint ini. Interpreter Python
untuk subprocess ke `app/machine-learning/` bisa di-override lewat env var
`ML_PYTHON_INTERPRETER` di `.env` (default: interpreter yang sama menjalankan
backend ini).

### 14. Login

Tidak ada endpoint register publik — user diprovisioning lewat
`scripts/seed_dev_user.py` (lihat Quick Start di atas untuk setup satu kali).

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

Response `200` berisi `token` (bearer, opaque — jangan didekode di frontend)
dan `user` (`name`/`role`/`initials`). Password salah atau username tidak
ditemukan -> `401`.

### 15. Profil user yang sedang login

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

Token tidak ada/tidak valid/kedaluwarsa -> `401` (bukan `403` — frontend hanya
treat `401` sebagai sinyal logout, lihat `core/dependencies.py`).

## Testing

```bash
pytest tests/ -q       # 56 test
```

Semua test jalan terhadap Postgres asli (bukan mock) — test yang butuh
skenario spesifik (AUTO vs MANUAL_REVIEW, offer OFFERED) menyisipkan baris
data throwaway lalu membersihkannya sendiri di teardown, jadi aman dijalankan
berkali-kali tanpa mengganggu data lain di database dev.

> ⚠️ **Dua jejak yang TIDAK dibersihkan** suite ini, diketahui dan berulang:
> deskripsi di `model_governance_config.cbs_weights` tertimpa jadi `"d"`, dan
> tersisa satu baris `model_governance_audit_log` dengan
> `performed_by='test.smoke.governance'`. Kalau Anda peduli pada isi kedua tabel
> itu, snapshot dulu sebelum menjalankan test, lalu restore setelahnya.

## Batasan yang diketahui

1. **Mayoritas endpoint tanpa autentikasi.** Tidak ada dependency auth global.
   Route `/customers` dan `/contracts` — termasuk semua data nasabah — terbuka
   tanpa token. Yang memakai `Depends(get_current_user)` hanya
   `PUT /ai-intelligence/weighting-parameters`, `POST /ai-intelligence/sync`, dan
   approve/reject di `/restructuring-groups`; ketiganya didokumentasikan sebagai
   syarat "ada user yang login" untuk audit trail, **bukan** gate role.
2. **Tidak ada RBAC.** Frontend menampilkan kelima menu ke setiap user yang login,
   termasuk Restructuring Approval dan AI Intelligence.
3. **`ai_reasoning` di `model_health` masih placeholder** (`available: false`
   tanpa syarat) — tabel `ai_reasoning_output` belum dibangun. Desainnya ada di
   `ai-reasoning-api-upgrade-tasks.md` (root repo) dan **belum siap
   diimplementasikan apa adanya**; baca bagian koreksi audit di dokumen itu
   sebelum mulai.
4. **AUC di kartu Model Health baru terisi setelah ~30 hari** riwayat scoring —
   itu AUC *live* (skor lampau vs pembayaran nyata sesudahnya), bukan AUC
   cross-validation saat training. `NULL` di instalasi baru adalah perilaku benar,
   dan sengaja tidak diganti angka training supaya tidak menyesatkan.
5. **Tidak ada endpoint register publik.** User diprovisioning lewat
   `scripts/seed_dev_user.py`.
6. **Tidak ada refresh-token flow** — `JWT_EXPIRE_MINUTES` efektif adalah durasi
   sesi sebelum user harus login ulang.
7. **`ML_PYTHON_INTERPRETER` menentukan interpreter subprocess Sync.** Kalau
   backend dan `app/machine-learning/` memakai venv berbeda, ini wajib diset —
   kalau tidak, training akan gagal dengan `ModuleNotFoundError` yang membingungkan.
8. **`helpers/database.py` di faker membaca env `PG*` sementara
   `app/machine-learning/config/settings.py` juga menghormati `COLLECTAI_DB_URL`.**
   Generator dan pipeline bisa menunjuk database berbeda kalau keduanya diset
   tidak konsisten.
9. **Quality check distribusi bersifat soft-fail secara default**
   (`COLLECTAI_STRICT_QC=false`), jadi `POST /ai-intelligence/sync` tidak lagi
   gagal hanya karena komposisi segmen bergeser. Pelanggaran tetap tercetak di
   log subprocess. Aktifkan hard-fail dengan `COLLECTAI_STRICT_QC=true`.
