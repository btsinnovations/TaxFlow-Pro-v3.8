"""Tests for application-level column encryption (P0.1)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.database import Base
from backend.tests.conftest import engine as test_engine, TestingSessionLocal
from backend import models
from backend.local.column_encryption import encrypt_for_user, decrypt_for_user
from backend.local.crypto import get_column_crypto_manager, clear_column_crypto_manager


def _reset_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def _create_user(db: Session, username: str = "encuser", password: str = "secret123"):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        return user, password
    from backend.local.crypto import LocalCryptoManager
    manager = LocalCryptoManager.create(password)
    user = models.User(
        username=username,
        email=f"{username}@local",
        hashed_password="$2b$12$fakefakefakefakefakefakefakefakefakefakefakefakefakef",
        encryption_salt=manager.salt_b64,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


def test_encryption_salt_set_at_boot(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!C0lumn-Crypt0-2026"})
    assert resp.status_code == 200
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).first()
        assert user is not None
        assert user.encryption_salt is not None
        assert len(user.encryption_salt) > 0
        manager = get_column_crypto_manager(user.id)
        assert manager is not None
    finally:
        db.close()


def test_client_tax_id_round_trip(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!C0lumn-Crypt0-2026"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/clients/", json={
        "name": "EncryptCo",
        "email": "enc@local",
        "tax_id": "12-3456789"
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tax_id"] == "12-3456789"
    client_id = data["id"]

    # Verify stored value is NOT plaintext
    db = TestingSessionLocal()
    try:
        row = db.query(models.Client).filter(models.Client.id == client_id).first()
        assert row is not None
        assert row.tax_id != "12-3456789"
        assert row.tax_id.startswith('{"v":')
    finally:
        db.close()

    # Read endpoint decrypts back to plaintext
    resp = client.get(f"/api/clients/{client_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["tax_id"] == "12-3456789"


def test_account_number_masked_round_trip(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!C0lumn-Crypt0-2026"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a client first (account requires client_id)
    resp = client.post("/api/clients/", json={"name": "Holder"}, headers=headers)
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", json={
        "name": "Checking",
        "institution": "Big Bank",
        "account_number_masked": "1234",
        "type": "checking",
        "client_id": client_id,
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_number_masked"] == "1234"
    account_id = data["id"]

    db = TestingSessionLocal()
    try:
        row = db.query(models.Account).filter(models.Account.id == account_id).first()
        assert row is not None
        assert row.account_number_masked != "1234"
        assert row.account_number_masked.startswith('{"v":')
    finally:
        db.close()

    resp = client.get(f"/api/accounts/{account_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["account_number_masked"] == "1234"


def test_logout_clears_crypto_manager(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!C0lumn-Crypt0-2026"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    db = TestingSessionLocal()
    try:
        user = db.query(models.User).first()
        assert get_column_crypto_manager(user.id) is not None
    finally:
        db.close()

    resp = client.post("/api/auth/logout", headers=headers)
    assert resp.status_code == 200

    db = TestingSessionLocal()
    try:
        user = db.query(models.User).first()
        assert get_column_crypto_manager(user.id) is None
    finally:
        db.close()


def test_decrypt_for_user_returns_plaintext_for_unencrypted_value(client: TestClient):
    """Legacy data that was never encrypted should be returned as-is."""
    _reset_db()
    db = TestingSessionLocal()
    try:
        user, password = _create_user(db)
        assert decrypt_for_user("plain-old-value", user) == "plain-old-value"
    finally:
        db.close()


def test_encrypt_decrypt_for_user_with_manager(client: TestClient):
    _reset_db()
    db = TestingSessionLocal()
    try:
        user, password = _create_user(db)
        from backend.local.crypto import register_column_crypto_manager
        register_column_crypto_manager(user.id, password, user.encryption_salt)

        encrypted = encrypt_for_user("sensitive-data", user)
        assert encrypted != "sensitive-data"
        assert encrypted.startswith('{"v":')

        decrypted = decrypt_for_user(encrypted, user)
        assert decrypted == "sensitive-data"
    finally:
        db.close()
