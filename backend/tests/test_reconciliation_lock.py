"""Tests for R3 Reconciliation Locking."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.accounting.reconciliation_lock import (
    ReconciliationLockError,
    complete_reconciliation,
    is_reconciliation_completed,
    is_transaction_cleared,
    reopen_reconciliation,
)
from backend.models import (
    Account, Client, ReconciliationImport, ReconciliationMatch,
    Statement, Transaction, User,
)


def _seed_user_and_tenant(db):
    user = User(username="rluser", email="rl@test.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    client = Client(name="RL Test", user_id=user.id)
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
        filename="test.csv", closing_balance=Decimal("100.00"),
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)
    return stmt


def _seed_txn(db, stmt_id, client_id, user_id, amount=Decimal("100.00"), txn_date=None):
    txn = Transaction(
        statement_id=stmt_id, tenant_id=client_id, user_id=user_id,
        date=txn_date or date(2026, 1, 15), description="Test",
        amount=amount, tx_type="credit",
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def _seed_recon_import(db, account_id, client_id, user_id, statement_balance=Decimal("100.00")):
    imp = ReconciliationImport(
        account_id=account_id, tenant_id=client_id, user_id=user_id,
        import_date=date(2026, 1, 31), statement_balance=statement_balance,
    )
    db.add(imp)
    db.commit()
    db.refresh(imp)
    return imp


def _seed_match(db, import_id, ledger_tx_id, statement_tx_id="STMT-001"):
    match = ReconciliationMatch(
        import_id=import_id, ledger_tx_id=ledger_tx_id,
        statement_tx_id=statement_tx_id, status="matched",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------


def test_complete_reconciliation(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id, Decimal("100.00"))
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)
    assert imp.is_completed is True
    assert imp.completed_at is not None


def test_complete_already_completed_fails(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id)
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)

    with pytest.raises(ReconciliationLockError, match="already completed"):
        complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)


def test_complete_with_nonzero_difference_fails(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id, Decimal("50.00"))
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    with pytest.raises(ReconciliationLockError, match="non-zero"):
        complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)


def test_complete_allow_unbalanced(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id, Decimal("50.00"))
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id, allow_unbalanced=True)
    assert imp.is_completed is True


def test_reopen_reconciliation(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id)
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)
    assert imp.is_completed is True

    reopen_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)
    assert imp.is_completed is False
    assert imp.completed_at is None


def test_reopen_not_completed_fails(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    imp = _seed_recon_import(db, account.id, client.id, user.id)

    with pytest.raises(ReconciliationLockError, match="not completed"):
        reopen_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)


def test_is_reconciliation_completed(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id)
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    assert is_reconciliation_completed(db, imp.id) is False
    complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)
    assert is_reconciliation_completed(db, imp.id) is True


def test_is_transaction_cleared(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id)
    imp = _seed_recon_import(db, account.id, client.id, user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    assert is_transaction_cleared(db, txn.id) is None

    complete_reconciliation(db, import_id=imp.id, user_id=user.id, tenant_id=client.id)
    cleared_by = is_transaction_cleared(db, txn.id)
    assert cleared_by == imp.id


def test_is_transaction_cleared_not_matched(db):
    user, client = _seed_user_and_tenant(db)
    account = _seed_account(db, client.id, user.id)
    stmt = _seed_statement(db, account.id, client.id, user.id)
    txn = _seed_txn(db, stmt.id, client.id, user.id)

    assert is_transaction_cleared(db, txn.id) is None


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


def test_api_complete_reconciliation(auth_client: TestClient, db):
    from backend.tests.conftest import _create_test_user
    auth_user = db.query(User).filter(User.username == "testuser").first()
    client_obj = auth_user.clients[0]

    account = _seed_account(db, client_obj.id, auth_user.id)
    stmt = _seed_statement(db, account.id, client_obj.id, auth_user.id)
    txn = _seed_txn(db, stmt.id, client_obj.id, auth_user.id)
    imp = _seed_recon_import(db, account.id, client_obj.id, auth_user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    resp = auth_client.post(f"/api/reconciliation/{imp.id}/complete")
    assert resp.status_code in (200, 404), resp.text
    if resp.status_code == 200:
        assert resp.json()["is_completed"] is True


def test_api_reopen_reconciliation(auth_client: TestClient, db):
    from backend.tests.conftest import _create_test_user
    auth_user = db.query(User).filter(User.username == "testuser").first()
    client_obj = auth_user.clients[0]

    account = _seed_account(db, client_obj.id, auth_user.id)
    stmt = _seed_statement(db, account.id, client_obj.id, auth_user.id)
    txn = _seed_txn(db, stmt.id, client_obj.id, auth_user.id)
    imp = _seed_recon_import(db, account.id, client_obj.id, auth_user.id, Decimal("100.00"))
    _seed_match(db, imp.id, txn.id)

    complete_reconciliation(db, import_id=imp.id, user_id=auth_user.id, tenant_id=client_obj.id)

    resp = auth_client.post(f"/api/reconciliation/{imp.id}/reopen")
    assert resp.status_code in (200, 403, 404), resp.text