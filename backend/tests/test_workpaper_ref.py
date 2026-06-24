"""Tests for workpaper reference links."""
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
        client_obj = models.Client(name="WP Client", user_id=user.id)
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)
        account = models.Account(
            name="Checking",
            institution="WP Bank",
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
            filename="wp.pdf",
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        tx = models.Transaction(
            statement_id=stmt.id,
            tenant_id=tenant_id,
            user_id=user_id,
            date=date(2025, 1, 15),
            description="Invoice",
            amount="250.00",
            tx_type="debit",
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx.id
    finally:
        db.close()


def _seed_gl_account(tenant_id: int, user_id: int, code: str, name: str, account_type: str = "expense"):
    db = TestingSessionLocal()
    try:
        acct = models.GLAccount(
            tenant_id=tenant_id, user_id=user_id, code=code, name=name, account_type=account_type
        )
        db.add(acct)
        db.commit()
        db.refresh(acct)
        return acct.id
    finally:
        db.close()


def _seed_gl_entry(tenant_id: int, user_id: int, date_val, debit_account_id=None, amount="0.00"):
    db = TestingSessionLocal()
    try:
        if isinstance(date_val, str):
            date_val = date.fromisoformat(date_val)
        entry = models.GeneralLedgerEntry(
            tenant_id=tenant_id, user_id=user_id, date=date_val,
            debit_account_id=debit_account_id, amount=amount
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry.id
    finally:
        db.close()


def test_set_workpaper_ref_on_transaction(auth_client):
    client = auth_client
    _, tenant_id, account_id = _seed_tenant(client)
    tx_id = _seed_transaction(account_id, tenant_id, 1)

    resp = client.put(
        f"/api/transactions/{tx_id}/workpaper-ref",
        params={"tenant_id": tenant_id},
        json={"workpaper_ref": "WP-2025-001"},
    )
    assert resp.status_code == 200
    assert resp.json()["workpaper_ref"] == "WP-2025-001"


def test_set_workpaper_ref_on_gl_entry(auth_client):
    client = auth_client
    _, tenant_id, _ = _seed_tenant(client)
    cash_id = _seed_gl_account(tenant_id, 1, "1000", "Cash", "asset")
    entry_id = _seed_gl_entry(tenant_id, 1, "2025-01-15", debit_account_id=cash_id, amount="100.00")

    resp = client.put(
        f"/api/ledger/entries/{entry_id}/workpaper-ref",
        params={"tenant_id": tenant_id},
        json={"workpaper_ref": "WP-GL-001"},
    )
    assert resp.status_code == 200
    assert resp.json()["workpaper_ref"] == "WP-GL-001"


def test_workpaper_ref_in_transaction_response(auth_client):
    client = auth_client
    _, tenant_id, account_id = _seed_tenant(client)
    tx_id = _seed_transaction(account_id, tenant_id, 1)

    client.put(
        f"/api/transactions/{tx_id}/workpaper-ref",
        params={"tenant_id": tenant_id},
        json={"workpaper_ref": "WP-2025-002"},
    )

    resp = client.get("/api/export/transactions", params={"tenant_id": tenant_id})
    assert resp.status_code == 200
    assert "WP-2025-002" in resp.text
