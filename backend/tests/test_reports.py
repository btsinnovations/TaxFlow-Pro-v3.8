"""Tests for the v3.11 Reports module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.reports import (
    profit_and_loss,
    trial_balance,
    balance_sheet,
    cash_flow_statement,
)


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


def test_balance_sheet_asset_liability_equity(db: Session):
    user, client = _seed_user_and_tenant(db)
    cash = create_account(db, client.id, user.id, "1010", "Cash", "asset")
    ap = create_account(db, client.id, user.id, "2010", "Accounts Payable", "liability")
    equity = create_account(db, client.id, user.id, "3010", "Retained Earnings", "equity")
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 10),
        description="Initial capital",
        amount=Decimal("1000.00"),
        tx_type="credit",
        coa_account_id=equity["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 12),
        description="Cash purchase",
        amount=Decimal("300.00"),
        tx_type="debit",
        coa_account_id=cash["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Bill owed",
        amount=Decimal("200.00"),
        tx_type="credit",
        coa_account_id=ap["id"],
    )

    result = balance_sheet(db, client.id, user.id, date(2026, 1, 31))
    assert result["total_assets"] == 300.0
    assert result["total_liabilities"] == 200.0
    assert result["total_equity"] == 1000.0
    assert result["liabilities_plus_equity"] == 1200.0


def test_balance_sheet_respects_as_of_date(db: Session):
    user, client = _seed_user_and_tenant(db)
    cash = create_account(db, client.id, user.id, "1020", "Cash", "asset")
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="January cash",
        amount=Decimal("100.00"),
        tx_type="debit",
        coa_account_id=cash["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 2, 5),
        description="February cash",
        amount=Decimal("50.00"),
        tx_type="debit",
        coa_account_id=cash["id"],
    )

    result = balance_sheet(db, client.id, user.id, date(2026, 1, 31))
    assert result["total_assets"] == 100.0


def test_cash_flow_statement_sections(db: Session):
    user, client = _seed_user_and_tenant(db)
    revenue = create_account(db, client.id, user.id, "4010", "Sales", "income")
    expense = create_account(db, client.id, user.id, "5100", "Rent", "expense")
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Sale",
        amount=Decimal("500.00"),
        tx_type="credit",
        coa_account_id=revenue["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 10),
        description="Rent",
        amount=Decimal("200.00"),
        tx_type="debit",
        coa_account_id=expense["id"],
    )

    result = cash_flow_statement(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["operating"] == 300.0
    assert result["investing"] == 0.0
    assert result["financing"] == 0.0
    assert result["net_change"] == 300.0


def test_pnl_uncategorized_fallback(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Sale no coa",
        amount=Decimal("250.00"),
        tx_type="credit",
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 8),
        description="Expense no coa",
        amount=Decimal("80.00"),
        tx_type="debit",
    )

    result = profit_and_loss(db, client.id, user.id, date(2026, 1, 1), date(2026, 1, 31))
    assert result["income"] == 250.0
    assert result["expenses"] == 80.0
    assert result["net"] == 170.0


def test_trial_balance_uncategorized_excluded(db: Session):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Uncategorized",
        amount=Decimal("100.00"),
        tx_type="debit",
    )
    rows = trial_balance(db, client.id, user.id, date(2026, 1, 31))
    # Uncategorized transactions have no COA, so no row is produced for them.
    assert all(r["code"] != "0000" for r in rows)


def test_coa_hierarchy_rollup_in_balance_sheet(db: Session):
    user, client = _seed_user_and_tenant(db)
    parent = create_account(db, client.id, user.id, "1100", "Receivables Parent", "asset")
    child = create_account(db, client.id, user.id, "1110", "Customer A", "asset", parent_id=parent["id"])
    account = _seed_account(db, client.id, user.id)

    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 5),
        description="Customer A invoice",
        amount=Decimal("400.00"),
        tx_type="debit",
        coa_account_id=child["id"],
    )

    result = balance_sheet(db, client.id, user.id, date(2026, 1, 31))
    asset_section = result["sections"]["assets"]
    assert asset_section["total"] == 400.0
    parent_row = next(n for n in asset_section["accounts"] if n["number"] == "1100")
    assert parent_row["balance"] == 400.0
    assert len(parent_row["children"]) == 1
    assert parent_row["children"][0]["number"] == "1110"


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


def test_api_balance_sheet(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    cash = create_account(db, client.id, auth_user.id, "1060", "Cash BS", "asset")
    equity = create_account(db, client.id, auth_user.id, "3020", "Equity BS", "equity")
    account = _seed_account(db, client.id, auth_user.id)
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 5, 1),
        description="Capital",
        amount=Decimal("1000.00"),
        tx_type="credit",
        coa_account_id=equity["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 5, 5),
        description="Deposit",
        amount=Decimal("600.00"),
        tx_type="debit",
        coa_account_id=cash["id"],
    )

    resp = auth_client.post("/api/reports/balance-sheet", params={"as_of": "2026-05-31"}, json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_assets"] == 600.0
    assert body["total_equity"] == 1000.0
    assert body["liabilities_plus_equity"] == 1000.0


def test_api_cash_flow(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    revenue = create_account(db, client.id, auth_user.id, "4020", "Service Revenue", "income")
    expense = create_account(db, client.id, auth_user.id, "5110", "Rent", "expense")
    account = _seed_account(db, client.id, auth_user.id)
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 6, 1),
        description="Service sale",
        amount=Decimal("900.00"),
        tx_type="credit",
        coa_account_id=revenue["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, auth_user.id,
        date=date(2026, 6, 2),
        description="Rent paid",
        amount=Decimal("100.00"),
        tx_type="debit",
        coa_account_id=expense["id"],
    )

    resp = auth_client.post("/api/reports/cash-flow", json={
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["operating"] == 800.0
    assert body["net_change"] == 800.0
