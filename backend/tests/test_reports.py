"""Tests for the v3.11 Reports module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.reports import profit_and_loss, trial_balance


def _seed_user_and_tenant(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "reportsuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="reportsuser",
        email="reports@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Reports Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


def _seed_account(db: Session, client_id: int, user_id: int):
    account = db.query(models.Account).filter(
        models.Account.client_id == client_id,
        models.Account.type == "checking",
    ).first()
    if account is None:
        account = models.Account(
            name="Checking",
            type="checking",
            client_id=client_id,
            tenant_id=client_id,
            user_id=user_id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def _seed_statement_and_txn(db: Session, account_id: int, tenant_id: int, user_id: int, **kwargs):
    statement = db.query(models.Statement).filter(models.Statement.account_id == account_id).first()
    if statement is None:
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="reports.csv",
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)
    txn = models.Transaction(
        statement_id=statement.id,
        tenant_id=tenant_id,
        user_id=user_id,
        **kwargs,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------

def test_profit_and_loss_zeros(db: Session):
    user, client = _seed_user_and_tenant(db)
    result = profit_and_loss(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["income"] == 0.0
    assert result["expenses"] == 0.0
    assert result["net"] == 0.0


def test_profit_and_loss_income_and_expense(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Sale",
        amount=Decimal("1000.00"),
        tx_type="credit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 10),
        description="Rent",
        amount=Decimal("400.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Supplies",
        amount=Decimal("100.00"),
        tx_type="debit",
    )

    result = profit_and_loss(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["income"] == 1000.0
    assert result["expenses"] == 500.0
    assert result["net"] == 500.0


def test_reports_respect_date_range(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 2, 1),
        description="Feb sale",
        amount=Decimal("500.00"),
        tx_type="credit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Jan expense",
        amount=Decimal("50.00"),
        tx_type="debit",
    )

    result = profit_and_loss(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["income"] == 0.0
    assert result["expenses"] == 50.0
    assert result["net"] == -50.0


def test_trial_balance_debits_equal_credits(db: Session):
    user, client = _seed_user_and_tenant(db)
    cash = create_account(db, client.id, user.id, "1000", "Cash", "asset")
    revenue = create_account(db, client.id, user.id, "4000", "Revenue", "income")
    expense = create_account(db, client.id, user.id, "5000", "Expense", "expense")
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Revenue",
        amount=Decimal("500.00"),
        tx_type="credit",
        coa_account_id=revenue["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 10),
        description="Expense",
        amount=Decimal("120.00"),
        tx_type="debit",
        coa_account_id=expense["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 12),
        description="Cash deposit",
        amount=Decimal("500.00"),
        tx_type="debit",
        coa_account_id=cash["id"],
    )

    rows = trial_balance(db, client.id, user.id, date(2026, 1, 31))
    by_code = {r["code"]: r for r in rows}
    assert by_code["1000"]["debit"] == 500.0
    assert by_code["4000"]["credit"] == 500.0
    assert by_code["5000"]["debit"] == 120.0
    total_debits = sum(r["debit"] for r in rows)
    total_credits = sum(r["credit"] for r in rows)
    assert total_debits == 620.0
    assert total_credits == 500.0


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Reports Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def test_api_profit_and_loss(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    account = _seed_account(db, client.id, auth_user.id)
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 4, 1),
        description="Sale",
        amount=Decimal("800.00"),
        tx_type="credit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 4, 5),
        description="Expense",
        amount=Decimal("200.00"),
        tx_type="debit",
    )

    resp = auth_client.post("/api/reports/profit-and-loss", json={
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["income"] == 800.0
    assert body["expenses"] == 200.0
    assert body["net"] == 600.0


def test_api_trial_balance(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    cash = create_account(db, client.id, auth_user.id, "1050", "Cash API", "asset")
    account = _seed_account(db, client.id, auth_user.id)
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 5, 1),
        description="Cash in",
        amount=Decimal("300.00"),
        tx_type="debit",
        coa_account_id=cash["id"],
    )

    resp = auth_client.post("/api/reports/trial-balance", params={"as_of": "2026-05-31"}, json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    rows = body["rows"]
    cash_row = next(r for r in rows if r["code"] == "1050")
    assert cash_row["debit"] == 300.0
