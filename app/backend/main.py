import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.v1.api import api_router
from core.config import settings

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("collectai.request_timing")

# TASK-P1: nol timing/logging sebelum ini di seluruh app/backend. Ambang
# "request lambat" — bisa dinaikkan lewat env kalau perlu, tapi default ini
# cukup untuk menangkap endpoint yang mulai melambat di rung data besar.
SLOW_REQUEST_THRESHOLD_S = 1.0

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
        "description": "Daftar Customer (filter chip + search + paginasi), detail 360° (join "
        "customer_master + customer_behavioral_standing + kontrak utama + skor AI-nya), dan "
        "daftar ringan kontrak milik 1 customer — sumbernya sama dengan yang dipakai "
        "app/machine-learning/ (Postgres, satu database).",
    },
    {
        "name": "contracts",
        "description": "Daftar Contract (filter/search/paginasi per-baris) dan detail penuh 1 "
        "kontrak: ringkasan, rincian outstanding, AI scoring, riwayat pembayaran, status "
        "restrukturisasi (read-only), plus timeline aktivitas (`activity-log`) yang dipakai "
        "bersama oleh Contract Detail dan expand kontrak di Customer Detail.",
    },
    {
        "name": "restructuring",
        "description": "Opsi restrukturisasi kredit: hitung tawaran on-demand per customer "
        "(REFINANCE/CONSOLIDATE/TAKEOVER), lalu catat keputusan customer "
        "(accept/reject). Kalkulasi angka tawaran murni dari "
        "`shared/restructuring_offer_calculator.py` — backend tidak pernah "
        "menghitung ulang logikanya sendiri.",
    },
    {
        "name": "restructuring-approval",
        "description": "Antrean approval supervisor untuk tawaran restrukturisasi tier "
        "MANUAL_REVIEW: lihat daftar per status, approve (GENERATED->OFFERED), atau reject "
        "(GENERATED->REJECTED). Setiap aksi tercatat di audit log (restructuring_approval_log). "
        "Tampil ke semua user login tanpa gate role (RBAC ditunda, lihat "
        "frontend-layout-upgrade-tasks.md TASK-A).",
    },
    {
        "name": "dashboard",
        "description": "Ringkasan lintas-tabel untuk halaman Dashboard: KPI, DPD buckets, "
        "contactability funnel + channel efficiency, restructuring pipeline snapshot, dan risk "
        "segment distribution — semua dihitung langsung dari data yang sama dipakai pipeline ML, "
        "tanpa tabel/materialized view tambahan.",
    },
    {
        "name": "ai-intelligence",
        "description": "Governance model scoring fase 1: Bobot CBS (baca/tulis "
        "`model_governance_config`, tabel baru milik backend ini) + Model Health gabungan "
        "(scoring model dari `model_monitoring_log`, AI Reasoning masih placeholder). Risk & "
        "Sub-model Threshold serta Restructuring Policy SENGAJA di luar scope fase ini — lihat "
        "frontend-layout-upgrade-tasks.md TASK-F.",
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

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """TASK-P1: instrumentasi timing request — sebelum ini backend tidak
    punya logging/timing sama sekali. Header ``X-Process-Time`` untuk
    inspeksi per-request (mis. lewat DevTools/k6 di TASK-P7); request yang
    melewati SLOW_REQUEST_THRESHOLD_S dicatat ke log supaya endpoint yang
    melambat di rung data besar (Area 1) tidak diam-diam lolos tanpa jejak."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_s = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{duration_s:.4f}"
    if duration_s >= SLOW_REQUEST_THRESHOLD_S:
        _logger.warning(
            "Slow request: %s %s took %.3fs", request.method, request.url.path, duration_s
        )
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Penanda service backend hidup dan bisa dijangkau. Di root (bukan di bawah "
    "/api/v1) karena ini urusan infra, bukan bagian dari API versi tertentu. Tidak menyentuh "
    "database atau layer lain sama sekali.",
)
def root_health():
    return {"service": settings.app_name, "status": "ok", "version": settings.app_version}
