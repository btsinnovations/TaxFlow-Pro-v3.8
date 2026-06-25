"""Tests for the v3.11 Tax Exports module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.tax_exports import schedule_c, set_mapping, list_mappings


def _seed_user_and_tenant(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "taxuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="taxuser",
        email="tax@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Tax Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


def _seed_statement_and_txn(db: Session, account_id: int, tenant_id: int, user_id: int, **kwargs):
    statement = db.query(models.Statement).filter(models.Statement.account_id == account_id).first()
    if statement is None:
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="tax.csv",
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

def test_set_mapping(db: Session):
    user, client = _seed_user_and_tenant(db)
    coa = create_account(db, client.id, user.id, "6100", "Advertising", "expense")
    mapping = set_mapping(db, client.id, user.id, coa["id"], "Schedule C", "8")
    assert mapping.id is not None
    assert mapping.coa_account_id == coa["id"]
    assert mapping.form == "Schedule C"
    assert mapping.line == "8"


def test_list_mappings(db: Session):
    user, client = _seed_user_and_tenant(db)
    coa_a = create_account(db, client.id, user.id, "6100", "Advertising", "expense")
    coa_b = create_account(db, client.id, user.id, "6200", "Office Expense", "expense")
    set_mapping(db, client.id, user.id, coa_a["id"], "Schedule C", "8")
    set_mapping(db, client.id, user.id, coa_b["id"], "Schedule C", "18")

    rows = list_mappings(db, client.id, user.id)
    assert len(rows) == 2
    assert {r.line for r in rows} == {"8", "18"}


def test_schedule_c_empty(db: Session):
    user, client = _seed_user_and_tenant(db)
    result = schedule_c(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["line_1_gross_receipts"] == 0.0
    assert result["line_28_total_expenses"] == 0.0
    assert result["line_31_net_profit"] == 0.0
    assert result["form"] == "Schedule C"


def test_schedule_c_sums_by_line(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = models.Account(
        name="Checking",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Advertising",
        amount=Decimal("100.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 10),
        description="Office Supplies",
        amount=Decimal("50.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Deposit",
        amount=Decimal("500.00"),
        tx_type="credit",
    )

    result = schedule_c(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["line_1_gross_receipts"] == 500.0
    assert result["line_28_total_expenses"] == 150.0
    assert result["line_31_net_profit"] == 350.0


def test_schedule_c_respects_date_range(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = models.Account(
        name="Checking",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 2, 1),
        description="Feb expense",
        amount=Decimal("75.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Jan income",
        amount=Decimal("200.00"),
        tx_type="credit",
    )

    result = schedule_c(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["line_1_gross_receipts"] == 200.0
    assert result["line_28_total_expenses"] == 0.0
    assert result["line_31_net_profit"] == 200.0


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

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


def test_api_create_mapping(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    coa = create_account(db, client.id, auth_user.id, "6150", "Advertising API", "expense")
    payload = {
        "coa_account_id": coa["id"],
        "form": "Schedule C",
        "line": "8",
        "description": "Ads",
    }
    resp = auth_client.post("/api/tax-exports/mappings", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["form"] == "Schedule C"
    assert body["line"] == "8"


def test_api_list_mappings(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    coa = create_account(db, client.id, auth_user.id, "6160", "Office API", "expense")
    set_mapping(db, client.id, auth_user.id, coa["id"], "Schedule C", "18")
    resp = auth_client.get("/api/tax-exports/mappings")
    assert resp.status_code == 200
    assert any(m["line"] == "18" for m in resp.json())


def test_api_schedule_c(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    account = models.Account(
        name="Tax Checking",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=auth_user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 3, 1),
        description="Sale",
        amount=Decimal("1000.00"),
        tx_type="credit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 3, 5),
        description="Supplies",
        amount=Decimal("120.00"),
        tx_type="debit",
    )

    resp = auth_client.post("/api/tax-exports/schedule-c", json={
        "start_date": "2026-03-01",
        "end_date": "2026-03-31",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["line_1_gross_receipts"] == 1000.0
    assert body["line_28_total_expenses"] == 120.0
    assert body["line_31_net_profit"] == 880.0
