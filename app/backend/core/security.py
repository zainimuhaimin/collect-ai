"""Utilitas kripto murni (hashing password, encode/decode JWT) — TIDAK
bergantung ke DB/repository/FastAPI apapun, supaya bisa dites terisolasi
dan tidak melanggar arah dependency (lihat services/auth_service.py)."""
from __future__ import annotations

import time

import bcrypt
import jwt

from core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    # Raises jwt.PyJWTError (ExpiredSignatureError, InvalidTokenError, dst.) kalau
    # bermasalah — pemanggil wajib menangkap ini dan mengubahnya jadi 401.
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
