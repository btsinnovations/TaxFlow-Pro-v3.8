"""Tests for the v3.10 -> v3.11 backup import wizard."""

from fastapi.testclient import TestClient

from backend import models


def _build_v3_10_backup():
    return {
        "version": "3.10.0",
        "users": [
            {
                "id": 1,
                "username": "legacy_user",
                "email": "legacy@example.com",
                "hashed_password": "hashed",
                "encryption_salt": "salt",
                "is_active": True,
                "created_at": "2026-01-01T12:00:00",
            }
        ],
        "clients": [
            {
                "id": 10,
                "name": "Legacy Client",
                "email": "client@example.com",
                "tax_id": "123-45-6789",
                "user_id": 1,
                "created_at": "2026-01-01T12:00:00",
            }
        ],
        "gl_accounts": [
            {
                "id": 100,
                "tenant_id": 10,
                "user_id": 1,
                "code": "5000",
                "name": "Office Supplies",
                "account_type": "expense",
                "created_at": "2026-01-01T12:00:00",
            }
        ],
        "accounts": [
            {
                "id": 200,
                "name": "Checking",
                "institution": "Test Bank",
                "account_number_masked": "1234",
                "type": "checking",
                "client_id": 10,
                "tenant_id": 10,
                "user_id": 1,
                "created_at": "2026-01-01T12:00:00",
            }
        ],
        "statements": [
            {
                "id": 300,
                "account_id": 200,
                "tenant_id": 10,
                "user_id": 1,
                "filename": "stmt.pdf",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "opening_balance": 100.0,
                "closing_balance": 200.0,
                "created_at": "2026-01-31T12:00:00",
            }
        ],
        "transactions": [
            {
                "id": 400,
                "statement_id": 300,
                "tenant_id": 10,
                "user_id": 1,
                "gl_account_id": 100,
                "date": "2026-01-15",
                "description": "Paper",
                "amount": -25.00,
                "tx_type": "debit",
                "category": "expense",
                "running_balance": 175.0,
                "created_at": "2026-01-15T12:00:00",
            }
        ],
    }


def test_import_backup_requires_auth(client: TestClient):
    """Unauthenticated requests cannot import backups."""
    response = client.post("/api/backup/import", json=_build_v3_10_backup())
    assert response.status_code == 401


def test_import_backup_single_user(auth_client: TestClient, db):
    """In single-user mode, import succeeds and remaps IDs."""
    response = auth_client.post("/api/backup/import", json=_build_v3_10_backup())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ok"]
    assert data["counts"]["users"] == 1
    assert data["counts"]["clients"] == 1
    assert data["counts"]["accounts"] == 1
    assert data["counts"]["statements"] == 1
    assert data["counts"]["transactions"] == 1
    assert data["counts"]["gl_accounts"] == 1

    # Verify remapped IDs differ from legacy IDs.
    assert data["id_maps"]["users"]["1"] != 1
    assert data["id_maps"]["clients"]["10"] != 10

    # Verify transaction was actually written.
    txns = db.query(models.Transaction).all()
    assert len(txns) == 1
    assert txns[0].description == "Paper"


def test_export_backup(auth_client: TestClient):
    """Export endpoint returns the current tenant's data in v3.11 format."""
    resp = auth_client.get("/api/backup/export")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["version"] == "3.11.0"
    assert data["tenant_id"] is not None
    assert len(data["users"]) >= 1
    assert len(data["clients"]) >= 1
    assert "exported_at" in data


def test_import_duplicate_users_are_mapped(auth_client: TestClient, db):
    """Importing the same backup twice skips duplicate users and maps existing ones."""
    backup = _build_v3_10_backup()
    r1 = auth_client.post("/api/backup/import", json=backup)
    assert r1.status_code == 200
    first_user_id = r1.json()["id_maps"]["users"]["1"]

    r2 = auth_client.post("/api/backup/import", json=backup)
    assert r2.status_code == 200
    second_user_id = r2.json()["id_maps"]["users"]["1"]
    assert first_user_id == second_user_id

    user_count = db.query(models.User).filter(models.User.username == "legacy_user").count()
    assert user_count == 1
