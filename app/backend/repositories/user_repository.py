"""Implementasi IUserRepository berbasis Postgres — tabel `users` dimiliki
oleh app/backend/ sendiri (lihat db/schema_users.sql), berbeda dari tabel
customer_master/dst yang dimiliki app/machine-learning/. Tetap satu Postgres
yang sama (satu sumber kredensial, lihat core/config.py)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from domain.models import User
from repositories.interfaces import IUserRepository

_SELECT = """
    SELECT id, username, password_hash, name, role, is_active
    FROM users
"""


def _row_to_user(row) -> User:
    return User(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        name=row.name,
        role=row.role,
        is_active=row.is_active,
    )


class UserRepository(IUserRepository):
    def __init__(self, engine: Engine):
        self._engine = engine

    def get_by_username(self, username: str) -> Optional[User]:
        with self._engine.connect() as conn:
            row = conn.execute(text(_SELECT + " WHERE username = :username"), {"username": username}).fetchone()
        return _row_to_user(row) if row else None

    def get_by_id(self, user_id: int) -> Optional[User]:
        with self._engine.connect() as conn:
            row = conn.execute(text(_SELECT + " WHERE id = :id"), {"id": user_id}).fetchone()
        return _row_to_user(row) if row else None

    def create(self, *, username: str, password_hash: str, name: str, role: str) -> User:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    "INSERT INTO users (username, password_hash, name, role) "
                    "VALUES (:username, :password_hash, :name, :role) "
                    "RETURNING id, username, password_hash, name, role, is_active"
                ),
                {"username": username, "password_hash": password_hash, "name": name, "role": role},
            ).fetchone()
        return _row_to_user(row)
