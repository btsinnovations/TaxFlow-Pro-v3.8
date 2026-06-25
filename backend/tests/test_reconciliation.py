"""Tests for the v3.11 Bank Reconciliation module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.reconciliation import (
    ReconciliationError,
    auto_match,
    import_statement,
    reconciliation_status,
)


def _seed_user_and_account(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "recuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="recuser",
        email="rec@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Rec Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)

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
    return user, client, account


def _seed_statement(account_id: int, tenant_id: int, user_id: int, filename="stmt.ofx"):
    stmt = models.Statement(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        filename=filename,
    )
    db = account_id  # placeholder to satisfy static analysis; we pass db directly below
    return stmt


def _seed_transaction(db: Session, account_id: int, tenant_id: int, user_id: int, **kwargs):
    # Ensure a statement exists for this account so we can create transactions.
    statement = db.query(models.Statement).filter(
        models.Statement.account_id == account_id,
    ).first()
    if statement is None:
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="rec.csv",
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)

    tx = models.Transaction(
        statement_id=statement.id,
        tenant_id=tenant_id,
        user_id=user_id,
        **kwargs,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------

def test_import_statement(db: Session):
    user, client, account = _seed_user_and_account(db)
    ri = import_statement(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        statement_balance=Decimal("1000.00"),
        statement_date=date(2026, 1, 31),
        filename="jan.ofx",
    )
    assert ri.id is not None
    assert ri.account_id == account.id
    assert ri.statement_balance == Decimal("1000.00")
    assert ri.statement_date == date(2026, 1, 31)


def test_reconciliation_status_no_matches(db: Session):
    user, client, account = _seed_user_and_account(db)
    _seed_transaction(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Deposit",
        amount=Decimal("250.00"),
        tx_type="debit",
    )
    ri = import_statement(
        db, client.id, user.id, account.id,
        Decimal("1000.00"), date(2026, 1, 31),
    )
    status = reconciliation_status(db, import_id=ri.id, user_id=user.id)
    assert status["statement_balance"] == 1000.0
    assert status["cleared"] == 0.0
    assert status["outstanding"] == 250.0
    assert status["difference"] == 1000.0


def test_auto_match_by_amount_and_date(db: Session):
    user, client, account = _seed_user_and_account(db)
    txn = _seed_transaction(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Deposit",
        amount=Decimal("250.00"),
        tx_type="debit",
    )
    ri = import_statement(
        db, client.id, user.id, account.id,
        Decimal("250.00"), date(2026, 1, 31),
    )
    matches = auto_match(
        db,
        import_id=ri.id,
        user_id=user.id,
        statement_rows=[{"id": "stmt-1", "date": "2026-01-15", "amount": 250.0}],
    )
    assert len(matches) == 1
    assert matches[0]["ledger_tx_id"] == txn.id
    assert matches[0]["match_type"] == "auto"


def test_auto_match_no_match_outside_window(db: Session):
    user, client, account = _seed_user_and_account(db)
    _seed_transaction(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 1),
        description="Deposit",
        amount=Decimal("100.00"),
        tx_type="debit",
    )
    ri = import_statement(
        db, client.id, user.id, account.id,
        Decimal("100.00"), date(2026, 1, 31),
    )
    matches = auto_match(
        db,
        import_id=ri.id,
        user_id=user.id,
        statement_rows=[{"id": "stmt-2", "date": "2026-01-25", "amount": 100.0}],
        date_window_days=3,
    )
    assert len(matches) == 0


def test_reconciliation_status_after_match(db: Session):
    user, client, account = _seed_user_and_account(db)
    _seed_transaction(
        db, account.id, client.id, user.id,
        date=date(2026, 1, 15),
        description="Deposit",
        amount=Decimal("250.00"),
        tx_type="debit",
    )
    ri = import_statement(
        db, client.id, user.id, account.id,
        Decimal("250.00"), date(2026, 1, 31),
    )
    auto_match(
        db,
        import_id=ri.id,
        user_id=user.id,
        statement_rows=[{"id": "stmt-3", "date": "2026-01-15", "amount": 250.0}],
    )
    status = reconciliation_status(db, import_id=ri.id, user_id=user.id)
    assert status["cleared"] == 250.0
    assert status["difference"] == 0.0


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Rec Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]

    account = db.query(models.Account).filter(
        models.Account.user_id == auth_user.id,
        models.Account.type == "checking",
    ).first()
    if account is None:
        account = models.Account(
            name="Auth Checking",
            type="checking",
            client_id=client.id,
            tenant_id=client.id,
            user_id=auth_user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return auth_user, client, account


def test_api_import_statement(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user(db)
    payload = {
        "account_id": account.id,
        "statement_balance": 5000.0,
        "statement_date": "2026-01-31",
        "filename": "api.ofx",
    }
    resp = auth_client.post("/api/reconciliation/import", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == account.id
    assert body["statement_balance"] == 5000.0


def test_api_auto_match(auth_client: TestClient, db: Session):
    auth_user, _, account = _ensure_auth_user(db)
    _seed_transaction(
        db, account.id, account.tenant_id, auth_user.id,
        date=date(2026, 1, 15),
        description="Deposit",
        amount=Decimal("123.45"),
        tx_type="debit",
    )
    payload = {
        "account_id": account.id,
        "statement_balance": 123.45,
        "statement_date": "2026-01-31",
    }
    resp = auth_client.post("/api/reconciliation/import", json=payload)
    import_id = resp.json()["id"]

    resp = auth_client.post(
        f"/api/reconciliation/{import_id}/auto-match",
        json={"statement_rows": [{"id": "api-1", "date": "2026-01-15", "amount": 123.45}]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["match_type"] == "auto"


def test_api_status(auth_client: TestClient, db: Session):
    auth_user, _, account = _ensure_auth_user(db)
    _seed_transaction(
        db, account.id, account.tenant_id, auth_user.id,
        date=date(2026, 1, 10),
        description="Payment",
        amount=Decimal("75.00"),
        tx_type="credit",
    )
    payload = {
        "account_id": account.id,
        "statement_balance": 75.0,
        "statement_date": "2026-01-31",
    }
    resp = auth_client.post("/api/reconciliation/import", json=payload)
    import_id = resp.json()["id"]
    resp = auth_client.get(f"/api/reconciliation/{import_id}/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["statement_balance"] == 75.0
    assert body["outstanding"] == 75.0
