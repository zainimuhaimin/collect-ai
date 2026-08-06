import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env di root repo (SATU file dipakai bersama oleh app/backend/,
# app/machine-learning/, app/core-banking/) — lihat .env.example.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_ENV_FILE = os.path.join(_REPO_ROOT, ".env")


class Settings(BaseSettings):
    """Konfigurasi aplikasi. Kredensial database dibaca dari .env di root
    repo — jangan hardcode kredensial di sini."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    app_name: str = "CollectAI Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    pghost: str = "localhost"
    pgport: str = "5432"
    pguser: str = "postgres"
    pgpassword: str = ""
    pgdatabase: str = "collect_ai"

    # Auth — token opaque di sisi frontend (tidak pernah di-decode di client),
    # jadi JWT stateless di sini sudah cukup, tidak perlu tabel session.
    jwt_secret: str = "dev-only-change-me-this-is-not-a-real-secret-32bytes"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 1 hari — frontend belum ada alur refresh token

    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # AI Intelligence Sync (services/ai_intelligence_sync_service.py) — subprocess
    # ke app/machine-learning/pipelines/*.py butuh interpreter Python yang tahu
    # dependency ML (pandas/sklearn/dst). Default kosong -> pakai sys.executable
    # (proses backend & ML share 1 venv saat ini) — TIDAK di-hardcode supaya
    # kedua app tetap bisa dipisah venv-nya nanti tanpa ubah kode.
    ml_python_interpreter: str = ""

    # AI Reasoning (ai-reasoning-api-upgrade-tasks.md) — LLM eksternal (Google
    # AI Studio/Gemini) untuk kartu narasi hyper-personalization di Customer
    # Detail. Beberapa key didukung sekaligus untuk rotasi otomatis saat quota
    # salah satu key habis (lihat services/gemini_client.py) — TIDAK menambah
    # dependency SDK baru, httpx yang sudah ada cukup untuk REST + responseSchema.
    # Default `ai_reasoning_enabled=False`: key yang belum diisi harus
    # menghasilkan respons "disabled" yang bersih, bukan error 500.
    google_ai_studio_api_keys: list[str] = []
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: float = 25.0   # HARUS < timeout klien (30s) — backend
                                            # menyerah dulu, bukan browser yang
                                            # menutup koneksi lebih dulu
    ai_reasoning_enabled: bool = False
    ai_reasoning_daily_call_limit: int = 300
    ai_reasoning_max_key_rotation_attempts: int = 3   # cap, bukan len(keys) —
                                                       # cegah latensi menumpuk
                                                       # kalau key dikonfigurasi banyak

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}"


settings = Settings()
