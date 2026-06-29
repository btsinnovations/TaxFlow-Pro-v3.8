"""Tests for adjusting-entry endpoint and report treatment (v3.11.6 R4)."""
from __future__ import annotations

import base64
import secrets

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.local.roles import Role, set_role


def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user is None:
        from backend.routers.auth import get_password_hash
        auth_user = models.User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("T4xFl0…2026"),
            is_active=True,
            encryption_salt=base64.b64encode(secrets.token_bytes(16)).decode("ascii"),
        )
        db.add(auth_user)
        db.commit()
        db.refresh(auth_user)
    if not auth_user.clients:
        client = models.Client(name="Adj Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def test_adjusting_entry_sets_entry_type(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    cash = create_account(db, client.id, user.id, "1010", "Cash", "asset")
    revenue = create_account(db, client.id, user.id, "4010", "Revenue", "income")
    payload = {
        "date": "2026-06-15",
        "description": "Accrue revenue",
        "debit_coa_account_id": cash["id"],
        "credit_coa_account_id": revenue["id"],
        "amount": 250.00,
        "memo": "Adjusting entry",
    }
    resp = auth_client.post("/api/ledger/adjusting-entry", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["entry_type"] == "adjusting"
    assert body["debit_coa_account_id"] == cash["id"]
    assert body["credit_coa_account_id"] == revenue["id"]
    assert body["amount"] == 250.0


def test_adjusting_entry_resolves_flag(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    flag = models.Flag(
        tenant_id=client.id,
        user_id=user.id,
        note="Reconcile me",
        created_by="test",
        resolved=False,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    cash = create_account(db, client.id, user.id, "1020", "Cash", "asset")
    revenue = create_account(db, client.id, user.id, "4020", "Revenue", "income")
    payload = {
        "date": "2026-06-15",
        "description": "Resolve flag",
        "debit_coa_account_id": cash["id"],
        "credit_coa_account_id": revenue["id"],
        "amount": 100.00,
        "review_flag_id": flag.id,
    }
    resp = auth_client.post("/api/ledger/adjusting-entry", json=payload)
    assert resp.status_code == 200, resp.text
    db.refresh(flag)
    assert flag.resolved is True
    assert flag.journal_entry_id == resp.json()["id"]


def test_viewer_cannot_create_adjusting_entry(client: TestClient, db: Session):
    user, _ = _ensure_auth_user(db)
    # Create a separate tenant owned by another user and grant the auth user
    # viewer role there. The single-tenant auth model always returns the first
    # user in the DB for any matching password, so we must keep ``user`` as
    # the first created user.
    from backend.routers.auth import get_password_hash
    owner = models.User(
        username="owner_t2",
        email="owner_t2@example.com",
        hashed_password=get_password_hash("T4xFl0…2026"),
        is_active=True,
        encryption_salt=base64.b64encode(secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    tenant2 = models.Client(name="Tenant 2", user_id=owner.id)
    db.add(tenant2)
    db.commit()
    db.refresh(tenant2)
    set_role(db, user.id, tenant2.id, Role.viewer, actor_user_id=owner.id)

    resp = client.post("/api/auth/login", data={"username": user.username, "password": "T4xFl0…2026"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    viewer_client = TestClient(client.app)
    viewer_client.headers.update({"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant2.id)})
    payload = {
        "date": "2026-06-15",
        "description": "Viewer attempt",
        "amount": 1.00,
    }
    resp = viewer_client.post("/api/ledger/adjusting-entry", json=payload)
    assert resp.status_code == 403


def test_regular_entry_endpoint_keeps_entry_type(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    cash = create_account(db, client.id, user.id, "1030", "Cash", "asset")
    revenue = create_account(db, client.id, user.id, "4030", "Revenue", "income")
    payload = {
        "date": "2026-06-15",
        "description": "Regular entry",
        "debit_coa_account_id": cash["id"],
        "credit_coa_account_id": revenue["id"],
        "amount": 50.00,
    }
    resp = auth_client.post("/api/ledger/entries", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["entry_type"] == "regular"
