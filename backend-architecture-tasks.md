# CollectAI — Backend Architecture (FastAPI) Task List

**Ini dikerjakan bersamaan/setelah** `restructuring-engine-tasks.md` dan
`restructuring_offer_calculator.py`. Backend ini yang menyajikan hasil kerja
ML module ke frontend, tapi backend TIDAK menghitung ulang logika bisnisnya —
dia hanya memanggil `ml/restructuring_offer_calculator.py` lewat service layer.

**Scaffold referensi terlampir** (`backend_scaffold.zip`) sudah:
- Diinstall (`fastapi`, `uvicorn`, `pydantic-settings`) dan **dites end-to-end**
  lewat `TestClient` — ke-4 endpoint di bawah terverifikasi jalan, termasuk
  kasus `MANUAL_REVIEW` yang tetap mengembalikan offer (bukan kosong).
- Pakai data in-memory (mock), BUKAN database nyata — lihat Catatan #2.

Salin struktur file dari scaffold ini langsung ke repo Anda sebagai starting point.

## Catatan untuk Agent

1. **Arsitektur berlapis, satu arah dependency**: Router → Service → Repository
   (interface). Router tidak boleh import repository sama sekali. Service tidak
   boleh import FastAPI (`Request`, `HTTPException`, dsb) — itu urusan router.
2. **Repository di scaffold ini pakai in-memory mock**, bukan Postgres asli.
   Saat integrasi DB nyata: buat class baru `PostgresCustomerRepository` dan
   `PostgresContractRepository` yang meng-implement interface yang sama di
   `repositories/interfaces.py`, lalu ganti wiring di `core/dependencies.py`
   SAJA. Service dan router tidak boleh disentuh — ini yang membuktikan DIP
   benar-benar dipakai, bukan cuma slogan.
3. **`ml/restructuring_offer_calculator.py` di scaffold ini HARUS diganti**
   dengan versi final dari `restructuring_offer_calculator.py` yang sudah
   diberikan sebelumnya (jika ada revisi lanjutan di situ, pakai yang terbaru).
   Modul itu murni Python, tidak boleh diimport balik oleh apapun di dalamnya
   ke FastAPI/backend — arah dependency-nya satu arah: backend depend ke ml/,
   bukan sebaliknya.
4. Endpoint 2 dan 3 di bawah masih pakai skema minimal (belum join ke CBS/
   scoring output) — itu memang scope TASK-62/63, bukan task ini.

**Urutan eksekusi:**
```
TASK-61 (struktur & config) → TASK-62 (repository + domain) → TASK-63 (service)
→ TASK-64 (router 1: health) → TASK-65 (router 2+3: customers)
→ TASK-66 (router 4: restructuring) → TASK-67 (wiring & main.py) → TASK-68 (tests)
```

---

## PHASE 15 — Backend Foundation

### TASK-61: Struktur Proyek & Konfigurasi
**Status**: [ ] Pending
**Dependencies**: -
**Output files**: `backend/core/config.py`, `backend/requirements.txt`, `backend/domain/models.py`

**Instruksi untuk agent:**
Buat struktur folder berikut (satu package per layer — ini yang menegakkan SRP
di level folder, bukan cuma niat):
```
backend/
├── main.py
├── requirements.txt
├── core/            # config.py, dependencies.py (DI wiring)
├── domain/          # models.py — dataclass murni, TIDAK bergantung Pydantic/FastAPI
├── schemas/         # Pydantic request/response models (boundary HTTP)
├── repositories/     # interfaces.py (abstrak) + implementasi konkret
├── services/         # business logic — depend ke repository interface, BUKAN implementasi
├── ml/               # modul kalkulasi murni (offer calculator) — lihat Catatan #3
└── api/v1/routers/   # satu file per resource (health.py, customers.py, restructuring.py)
```

```python
# domain/models.py
from dataclasses import dataclass

@dataclass
class Customer:
    cust_id: str
    name: str
    b_list_status: str
    restructure_count: int
    active_contract_count: int
    behavioral_grade: str

@dataclass
class Contract:
    contract_no: str
    cust_id: str
    product_type: str
    total_ots: float
    interest_rate: float
    remaining_tenor_months: int
    installment_amount: float
    dpd_current: int
    risk_segment: str
    recovery_score: float
    self_cure_probability: float
    closed_via_restructure: bool = False
```

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "CollectAI Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

settings = Settings()
```

```
# requirements.txt
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.0
pydantic-settings>=2.0
httpx>=0.27
```

**Acceptance Criteria:**
- [ ] `domain/models.py` tidak ada import dari `pydantic` atau `fastapi` — domain harus framework-agnostic
- [ ] `pip install -r requirements.txt` sukses tanpa konflik versi

---

### TASK-62: Repository Layer (Interface + In-Memory Implementation)
**Status**: [ ] Pending
**Dependencies**: TASK-61
**Output files**: `backend/repositories/interfaces.py`, `backend/repositories/in_memory_customer_repository.py`, `backend/repositories/in_memory_contract_repository.py`

**Instruksi untuk agent:**
Interface dipecah 2 (ISP) — jangan digabung jadi 1 `IRepository` besar.

```python
# repositories/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models import Contract, Customer

class ICustomerRepository(ABC):
    @abstractmethod
    def list_customers(self) -> List[Customer]: ...
    @abstractmethod
    def get_customer(self, cust_id: str) -> Optional[Customer]: ...

class IContractRepository(ABC):
    @abstractmethod
    def get_contract(self, contract_no: str) -> Optional[Contract]: ...
    @abstractmethod
    def get_primary_contract_for_customer(self, cust_id: str) -> Optional[Contract]: ...
    @abstractmethod
    def get_sibling_contracts(self, cust_id: str, exclude_contract_no: str) -> List[Contract]: ...
```

Implementasi in-memory: lihat `backend/repositories/in_memory_customer_repository.py`
dan `in_memory_contract_repository.py` di scaffold terlampir — salin langsung.

**Acceptance Criteria:**
- [ ] Kedua implementasi in-memory meng-inherit dan mengimplementasikan SEMUA method abstrak (Python akan raise `TypeError` saat instansiasi kalau tidak lengkap — jadikan ini bukti otomatis)
- [ ] Tidak ada logic bisnis di file ini — murni akses/simpan data

---

### TASK-63: Service Layer
**Status**: [ ] Pending
**Dependencies**: TASK-62, `restructuring_offer_calculator.py` (dari task ML sebelumnya)
**Output files**: `backend/services/customer_service.py`, `backend/services/restructuring_service.py`

**Instruksi untuk agent:**
`CustomerService` dan `RestructuringService` **hanya** menerima repository
lewat constructor (constructor injection) — jangan `import` implementasi
konkret repository di file ini, hanya `import` interface-nya.

`RestructuringService` bertugas MEMETAKAN `domain.models.Contract/Customer`
ke `ml.restructuring_offer_calculator.ContractInput/CustomerContext` sebelum
memanggil `assess_restructuring_options()` — lihat implementasi lengkap di
`backend/services/restructuring_service.py` pada scaffold terlampir.

**Acceptance Criteria:**
- [ ] `grep -r "InMemory" services/` tidak menemukan apa-apa (service tidak boleh tahu implementasi konkret repository)
- [ ] `grep -r "fastapi" services/` tidak menemukan apa-apa (service tidak boleh tahu HTTP)

---

## PHASE 16 — API Layer (4 Endpoint Contoh)

### TASK-64: Router 1 — Health Check
**Status**: [ ] Pending
**Dependencies**: TASK-61
**Output file**: `backend/api/v1/routers/health.py`

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/test")
def test_service():
    return {"message": "Hello from backend"}
```

**Acceptance Criteria:**
- [ ] `GET /api/v1/test` mengembalikan `{"message": "Hello from backend"}` dengan status 200

---

### TASK-65: Router 2 & 3 — Customer List & Detail
**Status**: [ ] Pending
**Dependencies**: TASK-63
**Output files**: `backend/api/v1/routers/customers.py`, `backend/schemas/customer.py`

**Instruksi untuk agent:**
```python
# schemas/customer.py
from pydantic import BaseModel

class CustomerSummary(BaseModel):
    cust_id: str
    name: str
    active_contract_count: int

class CustomerDetail(CustomerSummary):
    b_list_status: str
    behavioral_grade: str
```

Router meng-import `CustomerService` lewat `Depends(get_customer_service)`
(lihat `core/dependencies.py` di TASK-67) — router TIDAK PERNAH instansiasi
service atau repository secara langsung.

**Acceptance Criteria:**
- [ ] `GET /api/v1/customers` mengembalikan list, status 200
- [ ] `GET /api/v1/customers/{cust_id}` mengembalikan detail untuk id valid, 404 untuk id tidak ada

---

### TASK-66: Router 4 — Restructuring Options
**Status**: [ ] Pending
**Dependencies**: TASK-63, TASK-65
**Output files**: `backend/api/v1/routers/restructuring.py`, `backend/schemas/restructuring.py`

**Instruksi untuk agent:**
Ini adalah endpoint yang dispesifikasikan di TASK-58 (`restructuring-engine-tasks.md`).
Salin implementasi lengkap dari `backend/api/v1/routers/restructuring.py` di
scaffold terlampir — response HARUS menyertakan `eligibility_tier` dan
`eligibility_reasons`, bukan cuma `offers`, supaya frontend bisa menentukan
apakah tombol "tawarkan" aktif langsung atau perlu approval (lihat TASK-60).

**Acceptance Criteria:**
- [ ] `GET /api/v1/customers/{cust_id}/restructuring-options` mengembalikan `eligibility_tier`, `eligibility_reasons`, `offers`, `source`
- [ ] Tier `MANUAL_REVIEW` tetap mengembalikan `offers` terisi (regression test paling penting di sini — lihat TASK-51 poin 4)
- [ ] Tier `BLOCKED` (kalau ada test case-nya) mengembalikan `offers: []`

---

## PHASE 17 — Wiring & Verifikasi

### TASK-67: Dependency Injection Wiring + main.py
**Status**: [ ] Pending
**Dependencies**: TASK-62, TASK-63, TASK-64, TASK-65, TASK-66
**Output files**: `backend/core/dependencies.py`, `backend/main.py`, `backend/api/v1/api.py`

**Instruksi untuk agent:**
`core/dependencies.py` adalah **satu-satunya** file yang boleh meng-import
implementasi konkret repository (`InMemory...`) sekaligus interface-nya.
Ini yang membuat swap ke Postgres nanti jadi perubahan 1 file, bukan
perubahan menyebar ke seluruh codebase.

```python
# core/dependencies.py
from functools import lru_cache
from repositories.in_memory_customer_repository import InMemoryCustomerRepository
from repositories.in_memory_contract_repository import InMemoryContractRepository
from repositories.interfaces import ICustomerRepository, IContractRepository
from services.customer_service import CustomerService
from services.restructuring_service import RestructuringService

@lru_cache
def get_customer_repository() -> ICustomerRepository:
    return InMemoryCustomerRepository()

@lru_cache
def get_contract_repository() -> IContractRepository:
    return InMemoryContractRepository()

def get_customer_service() -> CustomerService:
    return CustomerService(get_customer_repository())

def get_restructuring_service() -> RestructuringService:
    return RestructuringService(get_customer_repository(), get_contract_repository())
```

**Acceptance Criteria:**
- [ ] `uvicorn main:app --reload` jalan tanpa error dari root `backend/`
- [ ] `GET /docs` (Swagger UI otomatis FastAPI) menampilkan ke-4 endpoint dengan benar

---

### TASK-68: Test End-to-End ke-4 Endpoint
**Status**: [ ] Pending
**Dependencies**: TASK-67
**Output file**: `backend/tests/test_smoke.py`

**Instruksi untuk agent:**
Pakai `fastapi.testclient.TestClient` — tidak perlu buka port beneran untuk
test ini. Salin dari `backend/tests/test_smoke.py` di scaffold terlampir
(sudah lulus 5 assertion saat dibuat, termasuk kasus MANUAL_REVIEW).

**Acceptance Criteria:**
- [ ] Semua 4 endpoint dites lewat `TestClient`, bukan cuma dibaca manual
- [ ] Test khusus untuk kasus `MANUAL_REVIEW` tidak boleh dihapus — ini regression guard paling penting di seluruh backend ini
