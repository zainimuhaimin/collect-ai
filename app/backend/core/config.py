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

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.pguser}:{self.pgpassword}@{self.pghost}:{self.pgport}/{self.pgdatabase}"


settings = Settings()
