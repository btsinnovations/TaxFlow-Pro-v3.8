"""Tests for the CSV export endpoints."""
from __future__ import annotations

import csv
import io
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
        client_obj = models.Client(name="Export Client", user_id=user.id)
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)

        account = models.Account(
            name="Checking",
            institution="Export Bank",
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


def _seed_transactions(account_id: int, tenant_id: int, user_id: int, dates: list):
    db = TestingSessionLocal()
    try:
        stmt = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="export.pdf",
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        for i, d in enumerate(dates):
            if isinstance(d, str):
                d = date.fromisoformat(d)
            db.add(models.Transaction(
                statement_id=stmt.id,
                tenant_id=tenant_id,
                user_id=user_id,
                date=d,
                description=f"Tx {i}",
                amount="100.00",
                tx_type="debit",
            ))
        db.commit()
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


def _seed_gl_entry(tenant_id: int, user_id: int, date_val, debit_account_id=None, credit_account_id=None, amount="0.00"):
    db = TestingSessionLocal()
    try:
        if isinstance(date_val, str):
            date_val = date.fromisoformat(date_val)
        entry = models.GeneralLedgerEntry(
            tenant_id=tenant_id, user_id=user_id, date=date_val,
            debit_account_id=debit_account_id, credit_account_id=credit_account_id, amount=amount
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry.id
    finally:
        db.close()


def test_export_transactions_csv(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant(client)
    _seed_transactions(account_id, tenant_id, user_id, ["2025-01-15", "2025-02-15"])

    resp = client.get("/api/export/transactions", params={"tenant_id": tenant_id})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["id", "date", "description", "amount", "type", "category", "workpaper_ref", "gl_account_id"]
    assert len(rows) == 3


def test_export_transactions_date_filter(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant(client)
    _seed_transactions(account_id, tenant_id, user_id, ["2025-01-15", "2025-02-15", "2025-03-15"])

    resp = client.get("/api/export/transactions", params={
        "tenant_id": tenant_id,
        "start_date": "2025-02-01",
        "end_date": "2025-03-01",
    })
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert len(rows) == 2  # header + one matching row


def test_export_general_ledger_csv(auth_client):
    client = auth_client
    user_id, tenant_id, _ = _seed_tenant(client)
    cash_id = _seed_gl_account(tenant_id, user_id, "1000", "Cash", "asset")
    expense_id = _seed_gl_account(tenant_id, user_id, "6000", "Expense", "expense")
    _seed_gl_entry(tenant_id, user_id, "2025-01-15", debit_account_id=cash_id, credit_account_id=expense_id, amount="50.00")

    resp = client.get("/api/export/general-ledger", params={"tenant_id": tenant_id})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["id", "date", "description", "debit_account_id", "credit_account_id", "amount", "memo", "workpaper_ref"]
    assert len(rows) == 2


def test_export_trial_balance_csv(auth_client):
    client = auth_client
    user_id, tenant_id, _ = _seed_tenant(client)
    cash_id = _seed_gl_account(tenant_id, user_id, "1000", "Cash", "asset")
    _seed_gl_entry(tenant_id, user_id, "2025-01-15", debit_account_id=cash_id, amount="100.00")

    resp = client.get("/api/export/trial-balance", params={"tenant_id": tenant_id, "as_of": "2025-12-31"})
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["account_id", "code", "name", "account_type", "balance"]
    assert any(row[0] == str(cash_id) for row in rows[1:])


def test_export_profit_loss_csv(auth_client):
    client = auth_client
    user_id, tenant_id, _ = _seed_tenant(client)
    income_id = _seed_gl_account(tenant_id, user_id, "4000", "Income", "income")
    expense_id = _seed_gl_account(tenant_id, user_id, "6000", "Expense", "expense")
    _seed_gl_entry(tenant_id, user_id, "2025-03-15", debit_account_id=income_id, amount="500.00")
    _seed_gl_entry(tenant_id, user_id, "2025-03-20", credit_account_id=expense_id, amount="200.00")

    resp = client.get("/api/export/profit-loss", params={
        "tenant_id": tenant_id,
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
    })
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["account_id", "code", "name", "account_type", "amount"]
    assert any("Net Income" in (row[2] if len(row) > 2 else "") for row in rows)


def test_export_balance_sheet_csv(auth_client):
    client = auth_client
    user_id, tenant_id, _ = _seed_tenant(client)
    cash_id = _seed_gl_account(tenant_id, user_id, "1000", "Cash", "asset")
    _seed_gl_entry(tenant_id, user_id, "2025-01-15", debit_account_id=cash_id, amount="1000.00")

    resp = client.get("/api/export/balance-sheet", params={"tenant_id": tenant_id, "as_of": "2025-12-31"})
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[0] == ["account_id", "code", "name", "account_type", "balance"]
    assert any("Total Assets" in (row[2] if len(row) > 2 else "") for row in rows)
