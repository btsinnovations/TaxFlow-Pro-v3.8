"""Tests for v3.11.03 Unified Register + Transactions module."""
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
        client_obj = models.Client(name="Register Client", user_id=user.id)
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)
        account = models.Account(
            name="Checking",
            institution="Register Bank",
            type="checking",
            client_id=client_obj.id,
            tenant_id=client_obj.id,
            user_id=user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        gl = models.GLAccount(
            tenant_id=client_obj.id,
            user_id=user.id,
            code="6100",
            name="Office Supplies",
            account_type="expense",
        )
        db.add(gl)
        db.commit()
        db.refresh(gl)
        return user.id, client_obj.id, account.id, gl.id
    finally:
        db.close()


def _seed_statement(account_id: int, tenant_id: int, user_id: int, opening_balance="0.00"):
    db = TestingSessionLocal()
    try:
        stmt = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="register.csv",
            opening_balance=opening_balance,
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        return stmt.id
    finally:
        db.close()


def _seed_transaction(statement_id: int, tenant_id: int, user_id: int, **kwargs):
    db = TestingSessionLocal()
    try:
        tx = models.Transaction(
            statement_id=statement_id,
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx.id
    finally:
        db.close()


def test_create_transaction_directly(auth_client):
    client = auth_client
    _, tenant_id, account_id, gl_id = _seed_tenant(client)

    resp = client.post(
        "/api/transactions/",
        params={"tenant_id": tenant_id},
        json={
            "date": "2025-06-01",
            "description": "Coffee",
            "amount": 4.50,
            "account_id": account_id,
            "tx_type": "debit",
            "category": "Meals",
            "gl_account_id": gl_id,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["description"] == "Coffee"
    assert body["amount"] == 4.50
    assert body["category"] == "Meals"
    assert body["gl_account_id"] == gl_id
    assert body["statement_id"]


def test_edit_transaction(auth_client):
    client = auth_client
    _, tenant_id, account_id, gl_id = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx_id = _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 2),
        description="Staples",
        amount="12.34",
        tx_type="debit",
        category="Office",
    )

    resp = client.patch(
        f"/api/transactions/{tx_id}",
        params={"tenant_id": tenant_id},
        json={
            "description": "Updated Staples",
            "amount": 99.99,
            "date": "2025-06-03",
            "category": "Supplies",
            "gl_account_id": gl_id,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["description"] == "Updated Staples"
    assert body["amount"] == 99.99
    assert body["date"] == "2025-06-03"
    assert body["category"] == "Supplies"
    assert body["gl_account_id"] == gl_id


def test_delete_transaction(auth_client):
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx_id = _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 4),
        description="Temp",
        amount="1.00",
        tx_type="debit",
    )

    resp = client.delete(
        f"/api/transactions/{tx_id}",
        params={"tenant_id": tenant_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    resp = client.get(
        "/api/transactions/",
        params={"tenant_id": tenant_id},
    )
    assert resp.status_code == 200
    assert not any(t["id"] == tx_id for t in resp.json())


def test_list_transactions_with_filters(auth_client):
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 5),
        description="Alpha",
        amount="10.00",
        tx_type="debit",
        category="A",
    )
    _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 6),
        description="Beta",
        amount="20.00",
        tx_type="debit",
        category="B",
    )

    resp = client.get(
        "/api/transactions/",
        params={"tenant_id": tenant_id, "account_id": account_id, "limit": 1},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(
        "/api/transactions/",
        params={"tenant_id": tenant_id, "q": "Beta"},
    )
    assert resp.status_code == 200
    assert all("Beta" in t["description"] for t in resp.json())


def test_running_balance_endpoint(auth_client):
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1, opening_balance="100.00")
    tx_id = _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 7),
        description="Deposit",
        amount="50.00",
        tx_type="debit",
    )
    _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 8),
        description="Payment",
        amount="25.00",
        tx_type="credit",
    )

    resp = client.get(
        f"/api/transactions/{tx_id}/running-balance",
        params={"tenant_id": tenant_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == account_id
    rows = body["rows"]
    assert len(rows) == 2
    assert rows[0]["running_balance"] == 150.00
    assert rows[1]["running_balance"] == 125.00


def test_running_balance_domain_helper(auth_client):
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1, opening_balance="0.00")
    _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 9),
        description="In",
        amount="10.00",
        tx_type="debit",
    )
    _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 10),
        description="Out",
        amount="3.00",
        tx_type="credit",
    )
    _seed_transaction(
        stmt_id, tenant_id, 1,
        date=date(2025, 6, 11),
        description="In2",
        amount="5.00",
        tx_type="debit",
    )

    from backend.accounting.register import compute_running_balance

    db_gen = TestingSessionLocal()
    try:
        rows = compute_running_balance(db_gen, account_id)
        balances = [r["running_balance"] for r in rows]
        assert balances == [10.00, 7.00, 12.00]
    finally:
        db_gen.close()
