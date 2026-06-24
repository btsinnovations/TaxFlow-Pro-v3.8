"""Tests for review flags."""
from __future__ import annotations

from datetime import date

from backend import models
from backend.tests.conftest import TestingSessionLocal


def _seed_tenant(client):
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "testuser").first()
        if user is None:
            user = models.User(
                username="testuser",
                email="test@example.com",
                hashed_password="fakehash",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        client_obj = models.Client(name="Flag Client", user_id=user.id)
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)
        account = models.Account(
            name="Checking",
            institution="Flag Bank",
            type="checking",
            client_id=client_obj.id,
            tenant_id=client_obj.id,
            user_id=user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return user.id, client_obj.id, account.id
    finally:
        db.close()


def _seed_transaction(account_id: int, tenant_id: int, user_id: int):
    db = TestingSessionLocal()
    try:
        stmt = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="flag.pdf",
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        tx = models.Transaction(
            statement_id=stmt.id,
            tenant_id=tenant_id,
            user_id=user_id,
            date=date(2025, 1, 15),
            description="Suspicious",
            amount="100.00",
            tx_type="debit",
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx.id
    finally:
        db.close()


def test_create_flag_on_transaction(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant(client)
    tx_id = _seed_transaction(account_id, tenant_id, user_id)

    resp = client.post("/api/flags/", params={"tenant_id": tenant_id}, json={
        "transaction_id": tx_id,
        "note": "Needs review",
        "created_by": "tester",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["transaction_id"] == tx_id
    assert data["note"] == "Needs review"
    assert data["resolved"] is False


def test_list_unresolved_flags(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant(client)
    tx_id = _seed_transaction(account_id, tenant_id, user_id)

    client.post("/api/flags/", params={"tenant_id": tenant_id}, json={
        "transaction_id": tx_id,
        "note": "Needs review",
        "created_by": "tester",
    })

    resp = client.get("/api/flags/", params={"tenant_id": tenant_id, "resolved": False})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get("/api/flags/", params={"tenant_id": tenant_id, "resolved": True})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_resolve_flag(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant(client)
    tx_id = _seed_transaction(account_id, tenant_id, user_id)

    resp = client.post("/api/flags/", params={"tenant_id": tenant_id}, json={
        "transaction_id": tx_id,
        "note": "Needs review",
        "created_by": "tester",
    })
    flag_id = resp.json()["id"]

    resp = client.put(f"/api/flags/{flag_id}/resolve", params={"tenant_id": tenant_id}, json={})
    assert resp.status_code == 200
    assert resp.json()["resolved"] is True
    assert resp.json()["resolved_at"] is not None


def test_reject_flag_without_target(auth_client):
    client = auth_client
    _, tenant_id, _ = _seed_tenant(client)

    resp = client.post("/api/flags/", params={"tenant_id": tenant_id}, json={
        "note": "Orphan flag",
        "created_by": "tester",
    })
    assert resp.status_code == 422
