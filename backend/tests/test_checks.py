"""Tests for the v3.11 Check Register module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.checks import CheckError, issue_check, list_checks, void_check


def _seed_user_and_account(db: Session):
    """Create user, tenant, and checking account for check tests."""
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "checksuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="checksuser",
        email="checks@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Checks Client", user_id=user.id)
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


# ---------------------------------------------------------------------------
# Domain logic tests
# ---------------------------------------------------------------------------

def test_issue_check_creates_transaction(db: Session):
    user, client, account = _seed_user_and_account(db)
    txn = issue_check(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        payee="Acme Supplies",
        amount=Decimal("123.45"),
        date_value=date(2026, 1, 15),
        memo="Invoice #101",
    )
    assert txn.id is not None
    assert txn.tx_type == "check"
    assert "Check #" in txn.description
    assert "Acme Supplies" in txn.description
    assert txn.amount == Decimal("123.45")
    assert txn.category == "check"
    assert txn.workpaper_ref.startswith("check:")

    # Verify synthetic statement.
    statement = db.query(models.Statement).filter(
        models.Statement.account_id == account.id,
        models.Statement.filename == "__checks__",
    ).first()
    assert statement is not None
    assert statement.tenant_id == client.id
    assert statement.user_id == user.id


def test_check_number_increments(db: Session):
    user, client, account = _seed_user_and_account(db)
    first = issue_check(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        payee="Payee A",
        amount=Decimal("10.00"),
        date_value=date(2026, 1, 1),
    )
    second = issue_check(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        payee="Payee B",
        amount=Decimal("20.00"),
        date_value=date(2026, 1, 2),
    )
    first_num = int(first.workpaper_ref.split(":")[1])
    second_num = int(second.workpaper_ref.split(":")[1])
    assert second_num == first_num + 1


def test_list_checks_filters_by_type(db: Session):
    user, client, account = _seed_user_and_account(db)

    # Create synthetic statement for a regular debit.
    debit_stmt = models.Statement(
        account_id=account.id,
        tenant_id=client.id,
        user_id=user.id,
        filename="stmt.csv",
    )
    db.add(debit_stmt)
    db.commit()
    db.refresh(debit_stmt)

    debit_txn = models.Transaction(
        statement_id=debit_stmt.id,
        tenant_id=client.id,
        user_id=user.id,
        date=date(2026, 1, 5),
        description="Debit purchase",
        amount=Decimal("5.00"),
        tx_type="debit",
    )
    db.add(debit_txn)

    check_txn = issue_check(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        payee="Check Payee",
        amount=Decimal("75.00"),
        date_value=date(2026, 1, 6),
    )
    db.commit()

    checks = list_checks(db, account_id=account.id, user_id=user.id)
    assert len(checks) == 1
    assert checks[0].id == check_txn.id
    assert checks[0].tx_type == "check"


def test_void_check(db: Session):
    user, client, account = _seed_user_and_account(db)
    txn = issue_check(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        payee="Void Target",
        amount=Decimal("50.00"),
        date_value=date(2026, 1, 10),
    )
    voided = void_check(db, transaction_id=txn.id, user_id=user.id, reason="Stop payment")
    assert voided.tx_type == "void"
    assert "VOIDED" in voided.description
    assert "Stop payment" in voided.description


def test_void_already_voided_fails(db: Session):
    user, client, account = _seed_user_and_account(db)
    txn = issue_check(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        payee="Double Void",
        amount=Decimal("30.00"),
        date_value=date(2026, 1, 11),
    )
    void_check(db, transaction_id=txn.id, user_id=user.id)
    with pytest.raises(CheckError, match="already voided"):
        void_check(db, transaction_id=txn.id, user_id=user.id)


def test_issue_check_invalid_account(db: Session):
    user, client, _ = _seed_user_and_account(db)
    with pytest.raises(CheckError, match="Account not found"):
        issue_check(
            db=db,
            tenant_id=client.id,
            user_id=user.id,
            account_id=999999,
            payee="No one",
            amount=Decimal("1.00"),
            date_value=date(2026, 1, 1),
        )


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user_has_client(db: Session):
    """Make the auth fixture user have at least one client + checking account."""
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Check Client", user_id=auth_user.id)
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


def test_api_issue_check(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_client(db)
    payload = {
        "account_id": account.id,
        "payee": "API Payee",
        "amount": 250.0,
        "date": "2026-02-01",
        "memo": "Rent check",
    }
    resp = auth_client.post("/api/checks/", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["description"].startswith("Check #")
    assert "API Payee" in body["description"]
    assert body["amount"] == 250.0
    assert body["workpaper_ref"].startswith("check:")


def test_api_list_checks(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_client(db)
    issue_check(
        db=db,
        tenant_id=account.tenant_id,
        user_id=account.user_id,
        account_id=account.id,
        payee="Listed Payee",
        amount=Decimal("99.99"),
        date_value=date(2026, 2, 15),
    )
    resp = auth_client.get(f"/api/checks/{account.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) >= 1
    assert all(item["tx_type"] == "check" for item in body)


def test_api_void_check(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_client(db)
    txn = issue_check(
        db=db,
        tenant_id=account.tenant_id,
        user_id=account.user_id,
        account_id=account.id,
        payee="Void API",
        amount=Decimal("44.44"),
        date_value=date(2026, 2, 20),
    )
    resp = auth_client.patch(f"/api/checks/{txn.id}/void", json={"reason": "Lost in mail"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tx_type"] == "void"
    assert "VOIDED" in body["description"]


def test_api_void_check_already_voided(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_client(db)
    txn = issue_check(
        db=db,
        tenant_id=account.tenant_id,
        user_id=account.user_id,
        account_id=account.id,
        payee="Double Void API",
        amount=Decimal("33.33"),
        date_value=date(2026, 2, 21),
    )
    auth_client.patch(f"/api/checks/{txn.id}/void", json={})
    resp = auth_client.patch(f"/api/checks/{txn.id}/void", json={})
    assert resp.status_code == 400
    assert "already voided" in resp.json()["detail"]


def test_api_issue_check_invalid_account(auth_client: TestClient, db: Session):
    _ensure_auth_user_has_client(db)
    payload = {
        "account_id": 999999,
        "payee": "No one",
        "amount": 1.0,
        "date": "2026-02-01",
    }
    resp = auth_client.post("/api/checks/", json=payload)
    assert resp.status_code == 404
    assert "Account not found" in resp.json()["detail"]


def test_api_requires_auth(client: TestClient):
    resp = client.get("/api/checks/1")
    assert resp.status_code == 401
