"""Tests for GL Bridge — R1 Remediation: double-entry auto-posting."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.accounting.gl_bridge import GLBridge
from backend.models import (
    Account, Client, CoaAccount, GeneralLedgerEntry, GLAccount,
    Statement, Transaction, User, CategorizationRule,
)


def _seed_user_and_tenant(db):
    user = User(username="gluser", email="gl@test.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    client = Client(name="GL Test", user_id=user.id)
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


def _seed_txn(db, stmt_id, client_id, user_id, **kwargs):
    txn = Transaction(
        statement_id=stmt_id, tenant_id=client_id, user_id=user_id,
        date=kwargs.get("date", date(2026, 1, 15)),
        description=kwargs.get("description", "Test transaction"),
        amount=kwargs.get("amount", Decimal("100.00")),
        tx_type=kwargs.get("tx_type", "credit"),
        coa_account_id=kwargs.get("coa_account_id"),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def _seed_coa(db, client_id, number, name, acct_type):
    coa = CoaAccount(tenant_id=client_id, number=number, name=name, type=acct_type)
    db.add(coa)
    db.commit()
    db.refresh(coa)
    return coa


def _seed_gl_account(db, client_id, user_id, code, name, acct_type="expense"):
    gl = GLAccount(tenant_id=client_id, user_id=user_id, code=code, name=name, account_type=acct_type)
    db.add(gl)
    db.commit()
    db.refresh(gl)
    return gl


def test_deposit_posts_debit_cash_credit_income(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    txn = _seed_txn(db, stmt.id, client.id, user.id, tx_type="credit", coa_account_id=income_coa.id)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)

    assert len(entries) == 2
    debit = [e for e in entries if e.debit_coa_account_id is not None][0]
    credit = [e for e in entries if e.credit_coa_account_id is not None][0]
    assert debit.amount == Decimal("100.00")
    assert credit.amount == Decimal("100.00")
    assert credit.credit_coa_account_id == income_coa.id


def test_withdrawal_posts_credit_cash_debit_expense(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    expense_coa = _seed_coa(db, client.id, 6200, "Office Supplies", "expense")
    txn = _seed_txn(db, stmt.id, client.id, user.id, tx_type="debit", amount=Decimal("50.00"), coa_account_id=expense_coa.id)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)

    assert len(entries) == 2
    debit = [e for e in entries if e.debit_coa_account_id is not None][0]
    credit = [e for e in entries if e.credit_coa_account_id is not None][0]
    assert debit.amount == Decimal("50.00")
    assert debit.debit_coa_account_id == expense_coa.id


def test_fallback_uncategorized_income(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id, tx_type="credit", coa_account_id=None)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)

    assert len(entries) == 2
    credit = [e for e in entries if e.credit_coa_account_id is not None][0]
    fallback = db.query(CoaAccount).filter(CoaAccount.tenant_id == client.id, CoaAccount.number == 4015).first()
    assert fallback is not None
    assert credit.credit_coa_account_id == fallback.id


def test_fallback_uncategorized_expense(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id, tx_type="debit", coa_account_id=None)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)

    assert len(entries) == 2
    debit = [e for e in entries if e.debit_coa_account_id is not None][0]
    fallback = db.query(CoaAccount).filter(CoaAccount.tenant_id == client.id, CoaAccount.number == 5015).first()
    assert fallback is not None
    assert debit.debit_coa_account_id == fallback.id


def test_idempotency_second_call_posts_nothing(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    txn = _seed_txn(db, stmt.id, client.id, user.id, coa_account_id=income_coa.id)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries1 = bridge.post_for_transaction(txn)
    db.commit()
    assert len(entries1) == 2

    entries2 = bridge.post_for_transaction(txn)
    assert len(entries2) == 0


def test_batch_posting(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")

    txns = []
    for i in range(5):
        t = _seed_txn(db, stmt.id, client.id, user.id, amount=Decimal(f"{100 + i}.00"), coa_account_id=income_coa.id)
        txns.append(t)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_batch(txns)
    assert len(entries) == 10


def test_zero_amount_skips_posting(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id, amount=Decimal("0.00"))

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)
    assert len(entries) == 0


def test_source_id_set(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    txn = _seed_txn(db, stmt.id, client.id, user.id, coa_account_id=income_coa.id)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)
    db.commit()
    for e in entries:
        assert e.source_id == f"txn:{txn.id}"


def test_entry_type_defaults_to_regular(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    txn = _seed_txn(db, stmt.id, client.id, user.id, coa_account_id=income_coa.id)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)
    for e in entries:
        assert e.entry_type == "regular"


def test_trial_balance_after_batch(db):
    """After posting 5 deposits and 3 withdrawals, debits should equal credits."""
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    income_coa = _seed_coa(db, client.id, 4010, "Sales Revenue", "income")
    expense_coa = _seed_coa(db, client.id, 6200, "Office Supplies", "expense")

    for i in range(5):
        _seed_txn(db, stmt.id, client.id, user.id, tx_type="credit", amount=Decimal("200.00"), coa_account_id=income_coa.id)
    for i in range(3):
        _seed_txn(db, stmt.id, client.id, user.id, tx_type="debit", amount=Decimal("100.00"), coa_account_id=expense_coa.id)

    all_txns = db.query(Transaction).filter(Transaction.tenant_id == client.id).all()
    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    bridge.post_batch(all_txns)

    all_entries = db.query(GeneralLedgerEntry).filter(GeneralLedgerEntry.tenant_id == client.id).all()
    total_debit = sum(Decimal(str(e.amount)) for e in all_entries if e.debit_coa_account_id is not None)
    total_credit = sum(Decimal(str(e.amount)) for e in all_entries if e.credit_coa_account_id is not None)
    assert total_debit == total_credit


def test_categorization_rule_match(db):
    """Transaction description matching a CategorizationRule uses the rule's COA account."""
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    office_coa = _seed_coa(db, client.id, 6200, "Office Supplies", "expense")
    gl_acct = _seed_gl_account(db, client.id, user.id, "6200", "Office Supplies", "expense")

    rule = CategorizationRule(
        tenant_id=client.id, user_id=user.id, name="Office",
        pattern="staples", gl_account_id=gl_acct.id, coa_account_id=office_coa.id,
        priority=10, enabled=True,
    )
    db.add(rule)
    db.commit()

    txn = _seed_txn(db, stmt.id, client.id, user.id, tx_type="debit", description="Staples order #123", coa_account_id=None)

    bridge = GLBridge(db, tenant_id=client.id, user_id=user.id)
    entries = bridge.post_for_transaction(txn)
    debit = [e for e in entries if e.debit_coa_account_id is not None][0]
    assert debit.debit_coa_account_id == office_coa.id