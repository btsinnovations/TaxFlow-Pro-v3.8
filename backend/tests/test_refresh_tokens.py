"""Refresh token rotation tests for TaxFlow Pro v3.9.2."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database import Base
from backend.tests.conftest import engine as test_engine


def _reset_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def _strong_password():
    return "T4xFl0w!Br0nze-V@ult-2026"


def test_boot_returns_access_and_refresh_tokens(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": _strong_password()})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_returns_access_and_refresh_tokens(client: TestClient):
    _reset_db()
    client.post("/api/auth/boot", json={"password": _strong_password()})

    resp = client.post("/api/auth/login", data={"username": "local", "password": _strong_password()})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_refresh_rotates_tokens(client: TestClient):
    _reset_db()
    boot = client.post("/api/auth/boot", json={"password": _strong_password()})
    old_refresh = boot.json()["refresh_token"]
    access = boot.json()["access_token"]

    # Access token works
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200

    # Exchange refresh token for a rotated pair
    resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    data = resp.json()
    new_access = data["access_token"]
    new_refresh = data["refresh_token"]
    assert new_refresh != old_refresh
    assert new_access != access

    # New tokens work
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200


def test_refresh_token_revoked_after_rotation(client: TestClient):
    _reset_db()
    boot = client.post("/api/auth/boot", json={"password": _strong_password()})
    old_refresh = boot.json()["refresh_token"]

    resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200

    # Reusing the old refresh token should now fail
    resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


def test_invalid_refresh_token_rejected(client: TestClient):
    _reset_db()
    client.post("/api/auth/boot", json={"password": _strong_password()})

    resp = client.post("/api/auth/refresh", json={"refresh_token": "***"})
    assert resp.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient):
    _reset_db()
    boot = client.post("/api/auth/boot", json={"password": _strong_password()})
    access = boot.json()["access_token"]
    refresh = boot.json()["refresh_token"]

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {access}"}, params={"refresh_token": refresh})
    assert resp.status_code == 200

    # Refresh token is now revoked
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401


def test_stolen_refresh_token_reuse_revokes_family(client: TestClient):
    """Detecting reuse of a rotated refresh token should kill the family."""
    _reset_db()
    boot = client.post("/api/auth/boot", json={"password": _strong_password()})
    refresh1 = boot.json()["refresh_token"]

    # First legitimate rotation
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 200
    refresh2 = resp.json()["refresh_token"]

    # Attacker reuses the old (stolen) refresh1 — should be rejected and family revoked.
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 401

    # Even the legitimate refresh2 (same family) should now be revoked.
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh2})
    assert resp.status_code == 401
