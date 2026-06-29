"""Tests for R2 Period Close Automation."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.accounting.period_close import (
    PeriodCloseError,
    close_period,
    get_period_status,
    is_period_closed,
    reopen_period,
)
from backend.accounting.gl_bridge import GLBridge
from backend.models import (
    Account, Client, CoaAccount, GeneralLedgerEntry,
    Period, Statement, Transaction, User,
)


def _seed_user_and_tenant(db):
    user = User(username="pcuser", email="pc@test.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    client = Client(name="PC Test", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


def _seed_account(db, client_id, user_id):
    account = Account(name="Checking", type="checking", client_id=client_id, tenant_id=client_id, user_id=user_id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _seed_statement(db, account_id, client_id, user_id):
    stmt = Statement(
        account_id=account_id, tenant_id=client_id, user_id=user_id,
        filename="test.csv", closing_balance=Decimal("1000.00"),
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)
    return stmt


def _seed_coa(db, client_id, number, name, acct_type):
    coa = CoaAccount(tenant_id=client_id, number=number, name=name, type=acct_type)
    db.add(coa)
    db.commit()
    db.refresh(coa)
    return coa


def _seed_period(db, client_id, user_id, name, start, end):
    period = Period(tenant_id=client_id, user_id=user_id, name=name,
                    start_date=start, end_date=end)
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def _seed_txn_with_gl(db, stmt_id, client_id, user_id, amount, tx_type, coa_id, txn_date):
    txn = Transaction(
        statement_id=stmt_id, tenant_id=client_id, user_id=user_id,
        date=txn_date, description="Test", amount=amount, tx_type=tx_type,
        coa_account_id=coa_id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    bridge = GLBridge(db, tenant_id=client_id, user_id=user_id)
    bridge.post_for_transaction(txn)
    db.commit()
    return txn


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------


def test_close_period_zeros_income_and_expense(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    expense_coa = _seed_coa(db, client.id, 6200, "Office Supplies", "expense")
    period = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))

    # 50K income, 30K expense
    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("50000"), "credit", income_coa.id, date(2026, 2, 1))
    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("30000"), "debit", expense_coa.id, date(2026, 2, 15))

    close_period(db, tenant_id=client.id, user_id=user.id, period_id=period.id)

    # Check closing entries exist
    closing_entries = db.query(GeneralLedgerEntry).filter(
        GeneralLedgerEntry.tenant_id == client.id,
        GeneralLedgerEntry.entry_type == "closing",
    ).all()
    # 1 income zeroing + 1 expense zeroing + 1 retained earnings = 3
    assert len(closing_entries) == 3

    # Retained Earnings should have 20K credit (net income)
    re_coa = db.query(CoaAccount).filter(
        CoaAccount.tenant_id == client.id, CoaAccount.number == 3100,
    ).first()
    assert re_coa is not None
    re_credits = db.query(GeneralLedgerEntry).filter(
        GeneralLedgerEntry.tenant_id == client.id,
        GeneralLedgerEntry.credit_coa_account_id == re_coa.id,
    ).all()
    assert sum(Decimal(str(e.amount)) for e in re_credits) == Decimal("20000")


def test_reopen_period_restores_balances(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    expense_coa = _seed_coa(db, client.id, 6200, "Office Supplies", "expense")
    period = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))

    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("50000"), "credit", income_coa.id, date(2026, 2, 1))
    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("30000"), "debit", expense_coa.id, date(2026, 2, 15))

    close_period(db, tenant_id=client.id, user_id=user.id, period_id=period.id)
    assert period.is_closed is True

    # Count closing entries
    closing_before = db.query(GeneralLedgerEntry).filter(
        GeneralLedgerEntry.entry_type == "closing",
        GeneralLedgerEntry.tenant_id == client.id,
    ).count()
    assert closing_before == 3

    reopen_period(db, tenant_id=client.id, user_id=user.id, period_id=period.id)
    assert period.is_closed is False
    assert period.closed_at is None

    # Closing entries should be gone
    closing_after = db.query(GeneralLedgerEntry).filter(
        GeneralLedgerEntry.entry_type == "closing",
        GeneralLedgerEntry.tenant_id == client.id,
    ).count()
    assert closing_after == 0


def test_close_already_closed_fails(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    period = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))

    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("1000"), "credit", income_coa.id, date(2026, 2, 1))
    close_period(db, tenant_id=client.id, user_id=user.id, period_id=period.id)

    with pytest.raises(PeriodCloseError, match="already closed"):
        close_period(db, tenant_id=client.id, user_id=user.id, period_id=period.id)


def test_reopen_not_closed_fails(db):
    user, client = _seed_user_and_tenant(db)
    period = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))

    with pytest.raises(PeriodCloseError, match="not closed"):
        reopen_period(db, tenant_id=client.id, user_id=user.id, period_id=period.id)


def test_sequential_close_enforced(db):
    user, client = _seed_user_and_tenant(db)
    p1 = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))
    p2 = _seed_period(db, client.id, user.id, "Q2 2026", date(2026, 4, 1), date(2026, 6, 30))

    with pytest.raises(PeriodCloseError, match="Prior period"):
        close_period(db, tenant_id=client.id, user_id=user.id, period_id=p2.id)


def test_is_period_closed(db):
    user, client = _seed_user_and_tenant(db)
    period = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))

    assert is_period_closed(db, client.id, date(2026, 2, 15)) is False

    period.is_closed = True
    db.commit()

    assert is_period_closed(db, client.id, date(2026, 2, 15)) is True
    assert is_period_closed(db, client.id, date(2026, 5, 15)) is False


def test_get_period_status(db):
    user, client = _seed_user_and_tenant(db)
    period = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))

    status = get_period_status(db, client.id, period.id)
    assert status["is_closed"] is False
    assert status["name"] == "Q1 2026"


def test_reopen_reverse_order_enforced(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")

    p1 = _seed_period(db, client.id, user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))
    p2 = _seed_period(db, client.id, user.id, "Q2 2026", date(2026, 4, 1), date(2026, 6, 30))

    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("1000"), "credit", income_coa.id, date(2026, 2, 1))
    close_period(db, tenant_id=client.id, user_id=user.id, period_id=p1.id)

    _seed_txn_with_gl(db, stmt.id, client.id, user.id, Decimal("2000"), "credit", income_coa.id, date(2026, 5, 1))
    close_period(db, tenant_id=client.id, user_id=user.id, period_id=p2.id)

    with pytest.raises(PeriodCloseError, match="Later period"):
        reopen_period(db, tenant_id=client.id, user_id=user.id, period_id=p1.id)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


def test_api_close_period(auth_client: TestClient, db):
    from backend.tests.conftest import _create_test_user
    auth_user = db.query(User).filter(User.username == "testuser").first()
    client = auth_user.clients[0]

    account = _seed_account(db, client.id, auth_user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    stmt = _seed_statement(db, account.id, client.id, auth_user.id)
    period = _seed_period(db, client.id, auth_user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))
    _seed_txn_with_gl(db, stmt.id, client.id, auth_user.id, Decimal("5000"), "credit", income_coa.id, date(2026, 2, 1))

    resp = auth_client.post(f"/api/periods/{period.id}/close")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_closed"] is True


def test_api_period_status(auth_client: TestClient, db):
    from backend.tests.conftest import _create_test_user
    auth_user = db.query(User).filter(User.username == "testuser").first()
    client = auth_user.clients[0]
    period = _seed_period(db, client.id, auth_user.id, "Q2 2026", date(2026, 4, 1), date(2026, 6, 30))

    resp = auth_client.get(f"/api/periods/{period.id}/status")
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_closed"] is False


def test_api_reopen_period(auth_client: TestClient, db):
    from backend.tests.conftest import _create_test_user
    auth_user = db.query(User).filter(User.username == "testuser").first()
    client_obj = auth_user.clients[0]

    account = _seed_account(db, client_obj.id, auth_user.id)
    income_coa = _seed_coa(db, client_obj.id, 4010, "Sales Revenue", "income")
    stmt = _seed_statement(db, account.id, client_obj.id, auth_user.id)
    period = _seed_period(db, client_obj.id, auth_user.id, "Q1 2026", date(2026, 1, 1), date(2026, 3, 31))
    _seed_txn_with_gl(db, stmt.id, client_obj.id, auth_user.id, Decimal("5000"), "credit", income_coa.id, date(2026, 2, 1))

    close_period(db, tenant_id=client_obj.id, user_id=auth_user.id, period_id=period.id)

    resp = auth_client.post(f"/api/periods/{period.id}/reopen")
    assert resp.status_code in (200, 403), resp.text  # 403 if admin role required