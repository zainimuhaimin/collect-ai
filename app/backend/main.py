from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.api import api_router
from core.config import settings

TAGS_METADATA = [
    {
        "name": "health",
        "description": "Cek service backend hidup dan bisa dijangkau.",
    },
    {
        "name": "auth",
        "description": "Login (username/password -> bearer token) dan profil user yang "
        "sedang login. Token opaque, tanpa alur refresh — expiry hanya diketahui lewat 401.",
    },
    {
        "name": "customers",
        "description": "Data customer & kontrak — sumbernya sama dengan yang dipakai "
        "app/machine-learning/ (Postgres, satu database).",
    },
    {
        "name": "restructuring",
        "description": "Opsi restrukturisasi kredit: hitung tawaran on-demand per customer "
        "(REFINANCE/CONSOLIDATE/TAKEOVER), lalu catat keputusan customer "
        "(accept/reject). Kalkulasi angka tawaran murni dari "
        "`shared/restructuring_offer_calculator.py` — backend tidak pernah "
        "menghitung ulang logikanya sendiri.",
    },
]

DESCRIPTION = """
Backend CollectAI — menyajikan data customer/kontrak dan opsi restrukturisasi
kredit ke frontend/CS, dengan sumber data Postgres yang sama dipakai
pipeline `app/machine-learning/`.

**Arsitektur berlapis** (satu arah dependency): Router → Service →
Repository (interface). Kalkulasi restrukturisasi murni ada di
`app/shared/restructuring_offer_calculator.py`, dipakai bersama oleh backend
ini dan pipeline ML.

**Alur restrukturisasi lengkap** (lihat tag `restructuring` untuk detail
tiap endpoint):
1. Batch harian ML (atau endpoint `GET .../restructuring-options` di sini
   secara on-demand) menghasilkan tawaran.
2. Customer merespons lewat `POST .../customer-response` — endpoint ini HANYA
   mencatat keputusan, tidak menghitung ulang apapun.
3. Kalau ACCEPTED, sistem core banking terpisah (`app/core-banking/`)
   mengeksekusi kontrak baru — backend tidak pernah membuat kontrak sendiri.
"""

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
)

# Tidak ada docker-compose/Vite dev-proxy di repo ini saat ini — kalau frontend
# dijalankan langsung lewat `npm run dev` (:5173), browser memanggil backend ini
# (:8000) cross-origin, jadi CORS wajib ada supaya request (termasuk header
# Authorization) tidak diblokir browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
