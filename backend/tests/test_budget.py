"""Tests for the v3.11 Budget module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.budget import budget_vs_actual, cash_flow_forecast, set_budget_line


def _seed_user_and_tenant(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "budgetuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="budgetuser",
        email="budget@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Budget Client", user_id=user.id)
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
            filename="budget.csv",
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

def test_set_budget_line(db: Session):
    user, client = _seed_user_and_tenant(db)
    coa = create_account(db, client.id, user.id, "5000", "Office Expense", "expense")
    line = set_budget_line(db, client.id, user.id, coa["id"], "2026-06", Decimal("500.00"))
    assert line.id is not None
    assert line.account_id == coa["id"]
    assert line.period == "2026-06"
    assert line.budget_amount == Decimal("500.00")


def test_budget_vs_actual(db: Session):
    user, client = _seed_user_and_tenant(db)
    coa = create_account(db, client.id, user.id, "5100", "Marketing", "expense")
    account = _seed_account(db, client.id, user.id)

    set_budget_line(db, client.id, user.id, coa["id"], "2026-06", Decimal("1000.00"))
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 6, 10),
        description="Ad spend",
        amount=Decimal("300.00"),
        tx_type="debit",
        gl_account_id=coa["id"],
    )

    result = budget_vs_actual(db, client.id, user.id, "2026-06")
    assert len(result) == 1
    assert result[0]["budget"] == 1000.0
    assert result[0]["actual"] == 300.0
    assert result[0]["variance"] == 700.0


def test_budget_vs_actual_respects_period(db: Session):
    user, client = _seed_user_and_tenant(db)
    coa = create_account(db, client.id, user.id, "5200", "Utilities", "expense")
    account = _seed_account(db, client.id, user.id)

    set_budget_line(db, client.id, user.id, coa["id"], "2026-06", Decimal("200.00"))
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 5, 15),
        description="May utility",
        amount=Decimal("80.00"),
        tx_type="debit",
        gl_account_id=coa["id"],
    )

    result = budget_vs_actual(db, client.id, user.id, "2026-06")
    assert len(result) == 1
    assert result[0]["budget"] == 200.0
    assert result[0]["actual"] == 0.0
    assert result[0]["variance"] == 200.0


def test_cash_flow_forecast_returns_projection(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)

    # Seed some historical transactions in the 3 months prior to start.
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2025, 10, 1),
        description="In",
        amount=Decimal("300.00"),
        tx_type="credit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2025, 11, 1),
        description="Out",
        amount=Decimal("100.00"),
        tx_type="debit",
    )

    result = cash_flow_forecast(db, client.id, user.id, date(2026, 1, 1), months=6)
    assert len(result) == 6
    for row in result:
        assert isinstance(row["month"], int)
        assert isinstance(row["projected_cash"], float)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Budget Auth Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def test_api_set_budget_line(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    coa = create_account(db, client.id, auth_user.id, "5300", "API Budget", "expense")
    payload = {"account_id": coa["id"], "period": "2026-07", "amount": 750.0}
    resp = auth_client.post("/api/budget/lines", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["period"] == "2026-07"
    assert body["budget_amount"] == 750.0


def test_api_budget_vs_actual(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    coa = create_account(db, client.id, auth_user.id, "5400", "API Actual", "expense")
    account = _seed_account(db, client.id, auth_user.id)
    set_budget_line(db, client.id, auth_user.id, coa["id"], "2026-08", Decimal("500.00"))
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 8, 5),
        description="Spend",
        amount=Decimal("150.00"),
        tx_type="debit",
        gl_account_id=coa["id"],
    )
    resp = auth_client.get("/api/budget/2026-08/vs-actual")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["budget"] == 500.0
    assert body[0]["actual"] == 150.0


def test_api_cash_flow_forecast(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    resp = auth_client.get("/api/budget/cash-flow", params={"start": "2026-01-01", "months": 6})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 6
    assert all(isinstance(r["projected_cash"], float) for r in body)
