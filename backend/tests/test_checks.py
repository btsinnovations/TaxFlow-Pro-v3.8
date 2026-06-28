"""Tests for the v3.11.6 B2.04 Check Register module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.checks import (
    CheckError,
    record_check,
    list_checks,
    get_check,
    update_check,
    mark_cleared,
    mark_reconciled,
    void_check,
    delete_check,
    search_by_number_range,
    issue_check,
)


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
        encryption_salt="test_salt",
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

def test_record_check(db: Session):
    """record_check creates a Check entry in the register."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(
        db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        check_number="1001", payee="Acme Supplies", amount=Decimal("123.45"),
        date_value=date(2026, 1, 15), memo="Invoice #101",
    )
    assert check.id is not None
    assert check.check_number == "1001"
    assert check.payee == "Acme Supplies"
    assert check.amount == Decimal("123.45")
    assert check.status == "pending"
    assert check.memo == "Invoice #101"


def test_record_check_duplicate_number(db: Session):
    """Duplicate check number for the same account should be rejected."""
    user, client, account = _seed_user_and_account(db)
    record_check(
        db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        check_number="1001", payee="First", amount=Decimal("10.00"),
        date_value=date(2026, 1, 1),
    )
    with pytest.raises(CheckError, match="Duplicate check number"):
        record_check(
            db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
            check_number="1001", payee="Second", amount=Decimal("20.00"),
            date_value=date(2026, 1, 2),
        )


def test_record_check_different_accounts_same_number(db: Session):
    """Same check number on different accounts should be allowed."""
    user, client, account = _seed_user_and_account(db)
    account2 = models.Account(
        name="Checking 2", type="checking",
        client_id=client.id, tenant_id=client.id, user_id=user.id,
    )
    db.add(account2)
    db.commit()
    db.refresh(account2)

    record_check(
        db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        check_number="1001", payee="A", amount=Decimal("10.00"),
        date_value=date(2026, 1, 1),
    )
    check2 = record_check(
        db=db, tenant_id=client.id, user_id=user.id, account_id=account2.id,
        check_number="1001", payee="B", amount=Decimal("20.00"),
        date_value=date(2026, 1, 2),
    )
    assert check2.check_number == "1001"


def test_record_check_invalid_account(db: Session):
    """Recording a check for a non-existent account should fail."""
    user, client, _ = _seed_user_and_account(db)
    with pytest.raises(CheckError, match="Account not found"):
        record_check(
            db=db, tenant_id=client.id, user_id=user.id, account_id=999999,
            check_number="1001", payee="No one", amount=Decimal("1.00"),
            date_value=date(2026, 1, 1),
        )


def test_list_checks(db: Session):
    """list_checks should return checks for the tenant."""
    user, client, account = _seed_user_and_account(db)
    record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                check_number="1001", payee="A", amount=Decimal("10"), date_value=date(2026, 1, 1))
    record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                check_number="1002", payee="B", amount=Decimal("20"), date_value=date(2026, 1, 2))

    checks = list_checks(db, tenant_id=client.id, account_id=account.id)
    assert len(checks) == 2
    assert checks[0].check_number == "1001"
    assert checks[1].check_number == "1002"


def test_list_checks_by_status(db: Session):
    """list_checks should filter by status."""
    user, client, account = _seed_user_and_account(db)
    c1 = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                     check_number="1001", payee="A", amount=Decimal("10"), date_value=date(2026, 1, 1))
    c2 = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                     check_number="1002", payee="B", amount=Decimal("20"), date_value=date(2026, 1, 2))
    mark_cleared(db, c2.id, client.id, user.id)

    pending = list_checks(db, tenant_id=client.id, account_id=account.id, status="pending")
    cleared = list_checks(db, tenant_id=client.id, account_id=account.id, status="cleared")
    assert len(pending) == 1
    assert pending[0].check_number == "1001"
    assert len(cleared) == 1
    assert cleared[0].check_number == "1002"


def test_search_by_number_range(db: Session):
    """search_by_number_range should return checks within the range."""
    user, client, account = _seed_user_and_account(db)
    for i in range(1001, 1006):
        record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                    check_number=str(i), payee=f"P{i}", amount=Decimal("10"),
                    date_value=date(2026, 1, i - 1000))

    results = search_by_number_range(db, tenant_id=client.id, account_id=account.id,
                                     start="1002", end="1004")
    assert len(results) == 3
    numbers = [c.check_number for c in results]
    assert numbers == ["1002", "1003", "1004"]


def test_mark_cleared(db: Session):
    """mark_cleared should set status to cleared."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                        check_number="1001", payee="A", amount=Decimal("10"),
                        date_value=date(2026, 1, 1))
    cleared = mark_cleared(db, check.id, client.id, user.id)
    assert cleared.status == "cleared"


def test_mark_reconciled(db: Session):
    """mark_reconciled should set status to reconciled."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                        check_number="1001", payee="A", amount=Decimal("10"),
                        date_value=date(2026, 1, 1))
    reconciled = mark_reconciled(db, check.id, client.id, user.id)
    assert reconciled.status == "reconciled"


def test_void_check(db: Session):
    """void_check should set status to void."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                        check_number="1001", payee="A", amount=Decimal("10"),
                        date_value=date(2026, 1, 1))
    voided = void_check(db, check.id, client.id, user.id, reason="Lost")
    assert voided.status == "void"
    assert "VOIDED" in (voided.memo or "")


def test_void_already_voided_fails(db: Session):
    """Voiding an already voided check should fail."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                        check_number="1001", payee="A", amount=Decimal("10"),
                        date_value=date(2026, 1, 1))
    void_check(db, check.id, client.id, user.id)
    with pytest.raises(CheckError, match="already voided"):
        void_check(db, check.id, client.id, user.id)


def test_delete_check(db: Session):
    """delete_check should remove the check entry."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                        check_number="1001", payee="A", amount=Decimal("10"),
                        date_value=date(2026, 1, 1))
    delete_check(db, check.id, client.id, user.id)
    assert get_check(db, check.id, client.id) is None


def test_update_check(db: Session):
    """update_check should update the check entry."""
    user, client, account = _seed_user_and_account(db)
    check = record_check(db, tenant_id=client.id, user_id=user.id, account_id=account.id,
                        check_number="1001", payee="A", amount=Decimal("10"),
                        date_value=date(2026, 1, 1))
    updated = update_check(db, check.id, client.id, user.id, payee="Updated Payee",
                         amount=Decimal("99.99"))
    assert updated.payee == "Updated Payee"
    assert updated.amount == Decimal("99.99")


def test_issue_check_creates_transaction_and_check(db: Session):
    """issue_check should create both a Transaction and a Check record."""
    user, client, account = _seed_user_and_account(db)
    txn = issue_check(
        db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        payee="Acme Supplies", amount=Decimal("123.45"),
        date_value=date(2026, 1, 15), memo="Invoice #101",
    )
    assert txn.id is not None
    assert txn.tx_type == "check"
    assert "Check #" in txn.description
    assert "Acme Supplies" in txn.description
    assert txn.amount == Decimal("123.45")

    # Verify Check record was also created.
    checks = list_checks(db, tenant_id=client.id, account_id=account.id)
    assert len(checks) == 1
    assert checks[0].payee == "Acme Supplies"
    assert checks[0].transaction_id == txn.id


def test_issue_check_duplicate_number(db: Session):
    """issue_check should reject duplicate check numbers."""
    user, client, account = _seed_user_and_account(db)
    issue_check(
        db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        payee="First", amount=Decimal("10"), date_value=date(2026, 1, 1),
        check_number="1001",
    )
    with pytest.raises(CheckError, match="Duplicate check number"):
        issue_check(
            db=db, tenant_id=client.id, user_id=user.id, account_id=account.id,
            payee="Second", amount=Decimal("20"), date_value=date(2026, 1, 2),
            check_number="1001",
        )


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user_has_client(db: Session):
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
            name="Auth Checking", type="checking",
            client_id=client.id, tenant_id=client.id, user_id=auth_user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return auth_user, client, account


def test_api_record_check(auth_client: TestClient, db: Session):
    """Test recording a check via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    payload = {
        "account_id": account.id,
        "check_number": "2001",
        "payee": "API Payee",
        "amount": 250.0,
        "date": "2026-02-01",
        "memo": "Rent check",
    }
    resp = auth_client.post("/api/checks/", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["check_number"] == "2001"
    assert body["payee"] == "API Payee"
    assert body["amount"] == 250.0
    assert body["status"] == "pending"


def test_api_record_check_duplicate(auth_client: TestClient, db: Session):
    """Test that duplicate check numbers are rejected by the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    payload = {
        "account_id": account.id,
        "check_number": "2002",
        "payee": "First",
        "amount": 100.0,
        "date": "2026-02-01",
    }
    resp = auth_client.post("/api/checks/", json=payload)
    assert resp.status_code == 201

    resp2 = auth_client.post("/api/checks/", json=payload)
    assert resp2.status_code == 409
    assert "Duplicate" in resp2.json()["detail"]


def test_api_list_checks(auth_client: TestClient, db: Session):
    """Test listing checks via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="3001", payee="Listed Payee",
        amount=Decimal("99.99"), date_value=date(2026, 2, 15),
    )
    resp = auth_client.get("/api/checks/", params={"account_id": account.id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) >= 1
    assert any(c["check_number"] == "3001" for c in body)


def test_api_get_check(auth_client: TestClient, db: Session):
    """Test getting a single check by ID."""
    _, _, account = _ensure_auth_user_has_client(db)
    check = record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="4001", payee="Get Payee",
        amount=Decimal("50.00"), date_value=date(2026, 3, 1),
    )
    resp = auth_client.get(f"/api/checks/{check.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == check.id
    assert body["payee"] == "Get Payee"


def test_api_clear_check(auth_client: TestClient, db: Session):
    """Test marking a check as cleared via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    check = record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="5001", payee="Clear Me",
        amount=Decimal("75.00"), date_value=date(2026, 3, 10),
    )
    resp = auth_client.patch(f"/api/checks/{check.id}/clear")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cleared"


def test_api_reconcile_check(auth_client: TestClient, db: Session):
    """Test marking a check as reconciled via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    check = record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="5002", payee="Reconcile Me",
        amount=Decimal("60.00"), date_value=date(2026, 3, 11),
    )
    resp = auth_client.patch(f"/api/checks/{check.id}/reconcile")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "reconciled"


def test_api_void_check(auth_client: TestClient, db: Session):
    """Test voiding a check via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    check = record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="5003", payee="Void Me",
        amount=Decimal("44.44"), date_value=date(2026, 3, 12),
    )
    resp = auth_client.patch(f"/api/checks/{check.id}/void", json={"reason": "Lost in mail"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "void"
    assert "VOIDED" in (body["memo"] or "")


def test_api_void_check_already_voided(auth_client: TestClient, db: Session):
    """Test that voiding an already voided check fails."""
    _, _, account = _ensure_auth_user_has_client(db)
    check = record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="5004", payee="Double Void",
        amount=Decimal("33.33"), date_value=date(2026, 3, 13),
    )
    auth_client.patch(f"/api/checks/{check.id}/void", json={})
    resp = auth_client.patch(f"/api/checks/{check.id}/void", json={})
    assert resp.status_code == 400
    assert "already voided" in resp.json()["detail"]


def test_api_delete_check(auth_client: TestClient, db: Session):
    """Test deleting a check via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    check = record_check(
        db=db, tenant_id=account.tenant_id, user_id=account.user_id,
        account_id=account.id, check_number="5005", payee="Delete Me",
        amount=Decimal("22.22"), date_value=date(2026, 3, 14),
    )
    resp = auth_client.delete(f"/api/checks/{check.id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True


def test_api_search_by_range(auth_client: TestClient, db: Session):
    """Test searching checks by number range via the API."""
    _, _, account = _ensure_auth_user_has_client(db)
    for i in range(6001, 6004):
        record_check(
            db=db, tenant_id=account.tenant_id, user_id=account.user_id,
            account_id=account.id, check_number=str(i), payee=f"P{i}",
            amount=Decimal("10"), date_value=date(2026, 4, i - 6000),
        )
    resp = auth_client.get("/api/checks/search/range", params={
        "account_id": account.id, "start": "6001", "end": "6002",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2


def test_api_issue_check_legacy(auth_client: TestClient, db: Session):
    """Test the legacy issue_check endpoint."""
    _, _, account = _ensure_auth_user_has_client(db)
    payload = {
        "account_id": account.id,
        "payee": "Legacy Payee",
        "amount": 150.0,
        "date": "2026-05-01",
        "memo": "Legacy check",
    }
    resp = auth_client.post("/api/checks/issue", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["description"].startswith("Check #")
    assert "Legacy Payee" in body["description"]
    assert body["amount"] == 150.0


def test_api_requires_auth(client: TestClient):
    resp = client.get("/api/checks/")
    assert resp.status_code == 401