"""Seed satu dev user yang bisa login — idempotent (aman dijalankan berkali-kali).

Tidak ada endpoint register publik di API ini (lihat schemas/auth.py,
api/v1/routers/auth.py) — provisioning user adalah operasi admin/internal,
makanya perlu script ini untuk bisa login sama sekali di environment baru.

Jalankan dari app/backend/:
    python -m scripts.seed_dev_user

Kredensial di bawah HANYA untuk dev lokal — jangan pernah diandalkan di
environment manapun selain local dev.
"""
from core.dependencies import get_engine
from core.security import hash_password
from repositories.user_repository import UserRepository

SEED_USERNAME = "admin"
SEED_PASSWORD = "admin123"
SEED_NAME = "Budi Santoso"
SEED_ROLE = "Regional Manager"


def main() -> None:
    repo = UserRepository(get_engine())

    existing = repo.get_by_username(SEED_USERNAME)
    if existing is not None:
        print(f"[seed] user '{SEED_USERNAME}' sudah ada — dilewati")
        return

    repo.create(
        username=SEED_USERNAME,
        password_hash=hash_password(SEED_PASSWORD),
        name=SEED_NAME,
        role=SEED_ROLE,
    )
    print(f"[seed] dev user '{SEED_USERNAME}' dibuat (name={SEED_NAME!r}, role={SEED_ROLE!r})")


if __name__ == "__main__":
    main()
