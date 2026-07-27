"""Test end-to-end lewat TestClient terhadap Postgres ASLI (sama seperti
test_smoke.py) — TIDAK ADA mock/in-memory repository. Fixture menyisipkan
1 baris user throwaway lalu membersihkannya di teardown.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from core.config import settings
from core.security import hash_password
from main import app

client = TestClient(app)

TEST_USERNAME = "test.auth.smoke"
TEST_PASSWORD = "testpass123"
TEST_NAME = "Test User"
TEST_ROLE = "QA Engineer"


@pytest.fixture(scope="module")
def engine():
    return create_engine(settings.database_url)


@pytest.fixture()
def test_user(engine):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": TEST_USERNAME})
        conn.execute(
            text(
                "INSERT INTO users (username, password_hash, name, role) "
                "VALUES (:u, :p, :n, :r)"
            ),
            {"u": TEST_USERNAME, "p": hash_password(TEST_PASSWORD), "n": TEST_NAME, "r": TEST_ROLE},
        )
    yield {"username": TEST_USERNAME, "password": TEST_PASSWORD}
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE username = :u"), {"u": TEST_USERNAME})


# ── POST /auth/login ──────────────────────────────────────────────────

def test_login_success(test_user):
    r = client.post("/api/v1/auth/login", json=test_user)
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["user"] == {"name": TEST_NAME, "role": TEST_ROLE, "initials": "TU"}


def test_login_wrong_password(test_user):
    r = client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": "wrongpassword"})
    assert r.status_code == 401


def test_login_unknown_user():
    r = client.post("/api/v1/auth/login", json={"username": "nobody-at-all", "password": "whatever"})
    assert r.status_code == 401


def test_login_rejects_empty_fields():
    r = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert r.status_code == 422


# ── GET /auth/me ───────────────────────────────────────────────────────

def test_me_with_valid_token(test_user):
    login = client.post("/api/v1/auth/login", json=test_user)
    token = login.json()["token"]

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"name": TEST_NAME, "role": TEST_ROLE, "initials": "TU"}


def test_me_without_token_is_401_not_403():
    """Regression guard: HTTPBearer default (auto_error=True) melempar 403,
    tapi frontend cuma treat 401 sebagai sinyal logout. Lihat core/dependencies.py."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_with_garbage_token():
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_me_with_expired_token():
    expired_payload = {"sub": "1", "iat": int(time.time()) - 120, "exp": int(time.time()) - 60}
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
