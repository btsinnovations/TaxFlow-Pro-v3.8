"""Tests for the v3.11 Tax Exports module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.tax_exports import (
    schedule_c,
    schedule_c_csv,
    set_mapping,
    delete_mapping,
    list_mappings,
    form_1099_nec_misc,
    year_end_summary,
)


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


def test_schedule_c_mapping_driven_lines(db: Session):
    user, client = _seed_user_and_tenant(db)
    income = create_account(db, client.id, user.id, "4010", "Sales", "income")
    expense = create_account(db, client.id, user.id, "6120", "Advertising", "expense")
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

    set_mapping(db, client.id, user.id, income["id"], "Schedule C", "1")
    set_mapping(db, client.id, user.id, expense["id"], "Schedule C", "8")

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Ad spend",
        amount=Decimal("120.00"),
        tx_type="debit",
        coa_account_id=expense["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 10),
        description="Sale",
        amount=Decimal("500.00"),
        tx_type="credit",
        coa_account_id=income["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 12),
        description="Fallback expense",
        amount=Decimal("80.00"),
        tx_type="debit",
    )

    result = schedule_c(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["line_1_gross_receipts"] == 500.0
    assert result["line_28_total_expenses"] == 200.0
    assert result["line_31_net_profit"] == 300.0
    assert result["lines"]["income"]["1"] == 500.0
    assert result["lines"]["expense"]["8"] == 120.0


def test_schedule_c_csv(db: Session):
    user, client = _seed_user_and_tenant(db)
    result = schedule_c(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    csv_text = schedule_c_csv(result)
    assert "form,year,line,description,amount" in csv_text
    assert "Schedule C,2026,31,Net profit" in csv_text


def test_1099_nec_misc(db: Session):
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
        date=date(2026, 3, 1),
        description="ABC Contractor",
        amount=Decimal("700.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 5, 1),
        description="Office Supplies Inc",
        amount=Decimal("100.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 6, 1),
        description="ABC Contractor",
        amount=Decimal("200.00"),
        tx_type="debit",
    )

    results = form_1099_nec_misc(db, client.id, user.id, 2026, threshold=Decimal("600"))
    assert len(results) == 1
    assert results[0]["payee"] == "ABC Contractor"
    assert results[0]["form"] == "1099-NEC"
    assert results[0]["amount"] == 900.0


def test_year_end_summary(db: Session):
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
        description="Consultant Jane",
        amount=Decimal("1000.00"),
        tx_type="debit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 4, 1),
        description="Sale",
        amount=Decimal("5000.00"),
        tx_type="credit",
    )

    summary = year_end_summary(db, client.id, user.id, 2026)
    assert summary["year"] == 2026
    assert summary["schedule_c"]["line_1_gross_receipts"] == 5000.0
    assert summary["schedule_c"]["line_28_total_expenses"] == 1000.0
    assert summary["total_reported_1099"] == 1000.0
    assert len(summary["form_1099s"]) == 1


def test_delete_mapping(db: Session):
    user, client = _seed_user_and_tenant(db)
    coa = create_account(db, client.id, user.id, "6110", "Travel", "expense")
    mapping = set_mapping(db, client.id, user.id, coa["id"], "Schedule C", "24a")
    assert delete_mapping(db, client.id, user.id, mapping.id) is True
    assert delete_mapping(db, client.id, user.id, mapping.id) is False
    assert list_mappings(db, client.id, user.id) == []


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


def test_api_1099(auth_client: TestClient, db: Session):
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
        date=date(2026, 7, 1),
        description="Freelance Writer",
        amount=Decimal("800.00"),
        tx_type="debit",
    )
    resp = auth_client.post("/api/tax-exports/1099?year=2026", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["payee"] == "Freelance Writer"
    assert body[0]["form"] == "1099-NEC"


def test_api_year_end_summary(auth_client: TestClient, db: Session):
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
        date=date(2026, 8, 1),
        description="Revenue",
        amount=Decimal("2000.00"),
        tx_type="credit",
    )
    resp = auth_client.post("/api/tax-exports/year-end-summary?year=2026", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["year"] == 2026
    assert body["schedule_c"]["line_1_gross_receipts"] == 2000.0


def test_api_delete_mapping(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    coa = create_account(db, client.id, auth_user.id, "6180", "Meals", "expense")
    mapping = set_mapping(db, client.id, auth_user.id, coa["id"], "Schedule C", "24b")
    resp = auth_client.delete(f"/api/tax-exports/mappings/{mapping.id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
