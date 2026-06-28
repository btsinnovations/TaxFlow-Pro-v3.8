"""Tests for v3.11.6 B2.01 — Unified Register + Transactions module."""
from __future__ import annotations

from datetime import date

from backend import models
from backend.tests.conftest import TestingSessionLocal
from backend.accounting.register import (
    list_transactions,
    bulk_delete,
    bulk_tag,
    bulk_change_status,
    set_transaction_status,
    add_tags,
    RegisterError,
)
from backend.local.roles import Role, has_role


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


# ---------------------------------------------------------------------------
# B2.01 Enhanced register tests: filters, sort, pagination, bulk, status, tags
# ---------------------------------------------------------------------------

def test_filter_by_date_range(auth_client):
    """Filter transactions by date range."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 6, 1), description="T1", amount="10", tx_type="debit")
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 6, 15), description="T2", amount="20", tx_type="debit")
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 6, 30), description="T3", amount="30", tx_type="debit")

    resp = client.get("/api/transactions/", params={
        "tenant_id": tenant_id, "start_date": "2025-06-10", "end_date": "2025-06-20"
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["description"] == "T2"


def test_filter_by_amount_range(auth_client):
    """Filter transactions by amount range."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 7, 1), description="Small", amount="5", tx_type="debit")
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 7, 2), description="Med", amount="50", tx_type="debit")
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 7, 3), description="Big", amount="500", tx_type="debit")

    resp = client.get("/api/transactions/", params={
        "tenant_id": tenant_id, "min_amount": 10, "max_amount": 100
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["description"] == "Med"


def test_filter_by_status(auth_client):
    """Filter transactions by status."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx1 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 8, 1), description="P", amount="10", tx_type="debit")
    tx2 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 8, 2), description="C", amount="20", tx_type="debit")
    # Set tx2 to cleared via domain helper
    db = TestingSessionLocal()
    try:
        set_transaction_status(db, tx2, tenant_id, 1, "cleared")
    finally:
        db.close()

    resp = client.get("/api/transactions/", params={
        "tenant_id": tenant_id, "status": "cleared"
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["description"] == "C"


def test_sort_by_amount_desc(auth_client):
    """Sort transactions by amount descending."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 9, 1), description="A", amount="10", tx_type="debit")
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 9, 2), description="B", amount="50", tx_type="debit")
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 9, 3), description="C", amount="30", tx_type="debit")

    resp = client.get("/api/transactions/", params={
        "tenant_id": tenant_id, "sort_by": "amount", "sort_order": "desc"
    })
    assert resp.status_code == 200
    body = resp.json()
    amounts = [t["amount"] for t in body]
    assert amounts == sorted(amounts, reverse=True)


def test_bulk_delete(auth_client):
    """Bulk delete transactions."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx1 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 10, 1), description="BD1", amount="10", tx_type="debit")
    tx2 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 10, 2), description="BD2", amount="20", tx_type="debit")

    resp = client.post("/api/transactions/bulk-delete", json={"transaction_ids": [tx1, tx2]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted"] == 2

    resp = client.get("/api/transactions/", params={"tenant_id": tenant_id})
    assert all(t["id"] not in [tx1, tx2] for t in resp.json())


def test_bulk_tag(auth_client):
    """Bulk add tags to transactions."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx1 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 11, 1), description="BT1", amount="10", tx_type="debit")
    tx2 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 11, 2), description="BT2", amount="20", tx_type="debit")

    resp = client.post("/api/transactions/bulk-tag", json={
        "transaction_ids": [tx1, tx2], "tags": ["urgent", "review"]
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2

    # Verify tags were applied
    db = TestingSessionLocal()
    try:
        tx = db.query(models.Transaction).filter(models.Transaction.id == tx1).first()
        assert "urgent" in (tx.tags or "")
        assert "review" in (tx.tags or "")
    finally:
        db.close()


def test_bulk_change_status(auth_client):
    """Bulk change status on transactions."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx1 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 12, 1), description="BS1", amount="10", tx_type="debit")
    tx2 = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 12, 2), description="BS2", amount="20", tx_type="debit")

    resp = client.post("/api/transactions/bulk-status", json={
        "transaction_ids": [tx1, tx2], "status": "cleared"
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2

    db = TestingSessionLocal()
    try:
        tx = db.query(models.Transaction).filter(models.Transaction.id == tx1).first()
        assert tx.status == "cleared"
    finally:
        db.close()


def test_set_status_endpoint(auth_client):
    """Set transaction status via the API."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx_id = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 6, 20), description="Status", amount="10", tx_type="debit")

    resp = client.patch(f"/api/transactions/{tx_id}/status", json={"status": "reconciled"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "reconciled"


def test_set_invalid_status_rejected(auth_client):
    """Invalid status should be rejected."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    tx_id = _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 6, 21), description="Bad", amount="10", tx_type="debit")

    resp = client.patch(f"/api/transactions/{tx_id}/status", json={"status": "bogus"})
    assert resp.status_code == 400


def test_domain_bulk_delete():
    """Test bulk_delete domain helper directly."""
    db = TestingSessionLocal()
    try:
        # Use the auth testuser setup
        user = db.query(models.User).filter(models.User.username == "testuser").first()
        if user is None:
            user = models.User(username="testuser", email="t@e.com", hashed_password="x", is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        c = models.Client(name="Bulk Test", user_id=user.id)
        db.add(c)
        db.commit()
        db.refresh(c)
        a = models.Account(name="BK", type="checking", client_id=c.id, tenant_id=c.id, user_id=user.id)
        db.add(a)
        db.commit()
        db.refresh(a)
        s = models.Statement(account_id=a.id, tenant_id=c.id, user_id=user.id, filename="bk.csv")
        db.add(s)
        db.commit()
        db.refresh(s)
        t1 = models.Transaction(statement_id=s.id, tenant_id=c.id, user_id=user.id, date=date(2025,1,1), description="X", amount="1", tx_type="debit")
        t2 = models.Transaction(statement_id=s.id, tenant_id=c.id, user_id=user.id, date=date(2025,1,2), description="Y", amount="2", tx_type="debit")
        db.add_all([t1, t2])
        db.commit()
        count = bulk_delete(db, [t1.id, t2.id], tenant_id=c.id, user_id=user.id)
        assert count == 2
    finally:
        db.close()


def test_domain_bulk_tag():
    """Test bulk_tag domain helper directly."""
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "testuser").first()
        if user is None:
            user = models.User(username="testuser", email="t@e.com", hashed_password="x", is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        c = models.Client(name="Tag Test", user_id=user.id)
        db.add(c)
        db.commit()
        db.refresh(c)
        a = models.Account(name="TG", type="checking", client_id=c.id, tenant_id=c.id, user_id=user.id)
        db.add(a)
        db.commit()
        db.refresh(a)
        s = models.Statement(account_id=a.id, tenant_id=c.id, user_id=user.id, filename="tg.csv")
        db.add(s)
        db.commit()
        db.refresh(s)
        t = models.Transaction(statement_id=s.id, tenant_id=c.id, user_id=user.id, date=date(2025,1,1), description="T", amount="1", tx_type="debit")
        db.add(t)
        db.commit()
        count = bulk_tag(db, [t.id], tenant_id=c.id, user_id=user.id, tags=["alpha"])
        assert count == 1
        db.refresh(t)
        assert "alpha" in (t.tags or "")
    finally:
        db.close()


def test_tenant_isolation_register(auth_client):
    """Transactions from one tenant should not be visible to another."""
    client = auth_client
    _, tenant_id, account_id, _ = _seed_tenant(client)
    stmt_id = _seed_statement(account_id, tenant_id, 1)
    _seed_transaction(stmt_id, tenant_id, 1, date=date(2025, 6, 1), description="Secret", amount="100", tx_type="debit")

    # Create a second tenant
    db = TestingSessionLocal()
    try:
        user2 = models.User(username="other", email="o@e.com", hashed_password="x", is_active=True, encryption_salt="x")
        db.add(user2)
        db.commit()
        db.refresh(user2)
        c2 = models.Client(name="Other", user_id=user2.id)
        db.add(c2)
        db.commit()
        db.refresh(c2)
        a2 = models.Account(name="O", type="checking", client_id=c2.id, tenant_id=c2.id, user_id=user2.id)
        db.add(a2)
        db.commit()
        db.refresh(a2)
        s2 = models.Statement(account_id=a2.id, tenant_id=c2.id, user_id=user2.id, filename="o.csv")
        db.add(s2)
        db.commit()
        db.refresh(s2)
        t2 = models.Transaction(statement_id=s2.id, tenant_id=c2.id, user_id=user2.id, date=date(2025,6,1), description="Other Tx", amount="50", tx_type="debit")
        db.add(t2)
        db.commit()

        # List transactions for the first tenant
        txns = list_transactions(db, tenant_id)
        assert all(tx.tenant_id == tenant_id for tx in txns)
        assert not any(tx.description == "Other Tx" for tx in txns)
    finally:
        db.close()
