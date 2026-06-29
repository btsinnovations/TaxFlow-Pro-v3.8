"""Tests for vendor management (v3.11.6 R5)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account


def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Tax Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def test_api_create_vendor(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    coa = create_account(db, client.id, user.id, "5180", "Contractors", "expense")
    payload = {
        "name": "Acme Supplies",
        "tax_id": "12-3456789",
        "is_1099_eligible": True,
        "default_expense_coa_account_id": coa["id"],
    }
    resp = auth_client.post("/api/vendors", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Acme Supplies"
    assert body["is_1099_eligible"] is True


def test_api_list_vendors(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    resp = auth_client.get("/api/vendors?is_1099_eligible=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(v["is_1099_eligible"] for v in body)
