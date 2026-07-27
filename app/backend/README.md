# CollectAI Backend

Backend FastAPI yang menyajikan data customer/kontrak dan opsi restrukturisasi
kredit. Sumber datanya adalah **Postgres yang sama** dipakai pipeline
`app/machine-learning/` — tidak ada mock/in-memory repository, semua endpoint
membaca/menulis ke database asli.

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
│   │                                # IRestructuringOfferRepository
│   ├── customer_repository.py      # implementasi Postgres
│   ├── contract_repository.py      # implementasi Postgres
│   └── restructuring_offer_repository.py  # implementasi Postgres
├── services/                       # business logic, depend ke interface saja
├── api/v1/routers/                 # health.py, customers.py, restructuring.py
└── tests/test_smoke.py             # end-to-end lewat TestClient, DB asli
```

Kalkulasi restrukturisasi (haircut, NPV, guardrail, dst) **tidak ada di
backend ini** — itu murni ada di `app/shared/restructuring_offer_calculator.py`,
dipakai bersama oleh backend dan pipeline ML lewat `RestructuringService`.

## Quick Start

```bash
# 1. Install dependencies (dari root repo, venv yang sama dipakai app/machine-learning/)
cd app/backend
pip install -r requirements.txt

# 2. Pastikan .env ada di ROOT repo (bukan di app/backend/) — lihat .env.example
#    Kredensial ini dipakai bersama oleh backend, machine-learning, dan core-banking.
cat ../../.env.example   # copy jadi ../../.env kalau belum ada, isi kredensial asli

# 3. Jalankan server
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
curl http://localhost:8000/api/v1/test
```

### 2. Daftar semua customer

```bash
curl http://localhost:8000/api/v1/customers
```

### 3. Detail satu customer

```bash
curl http://localhost:8000/api/v1/customers/CUST-00029
```

### 4. Opsi restrukturisasi (on-demand)

```bash
curl http://localhost:8000/api/v1/customers/CUST-00029/restructuring-options
```

Perhatikan `eligibility_tier` di response:
- `AUTO` — `offers` boleh langsung ditawarkan
- `MANUAL_REVIEW` — `offers` tetap terisi, tapi tunggu approval supervisor
- `BLOCKED` — `offers` selalu kosong (data kontrak tidak valid)

### 5. Customer merespons tawaran (accept/reject)

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

## Testing

```bash
pytest tests/ -v
```

Semua test jalan terhadap Postgres asli (bukan mock) — test yang butuh
skenario spesifik (AUTO vs MANUAL_REVIEW, offer OFFERED) menyisipkan baris
data throwaway lalu membersihkannya sendiri di teardown, jadi aman dijalankan
berkali-kali tanpa mengganggu data lain di database dev.
