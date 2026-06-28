"""Tests for the v3.11 Liabilities module (loans + credit lines)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.liabilities import (
    LiabilityError,
    compute_amortization_schedule,
    create_loan_schedule,
    credit_line_available,
)


def _seed_user_and_account(db: Session, account_type="loan"):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "liabuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="liabuser",
        email="liab@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Liab Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)

    account = models.Account(
        name="Loan Account",
        type=account_type,
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return user, client, account


# ---------------------------------------------------------------------------
# Amortization math
# ---------------------------------------------------------------------------

def test_amortization_schedule_math():
    schedule = compute_amortization_schedule(
        principal=Decimal("12000.00"),
        annual_rate=Decimal("0.06"),
        term_months=12,
        start_date=date(2026, 1, 1),
    )
    assert len(schedule) == 12
    first = schedule[0]
    assert first["month"] == 1
    assert first["payment"] == 1032.80  # implementation rounds down to cents
    assert first["interest"] == 60.00
    assert first["principal"] == 972.80
    assert first["balance"] == 11027.20

    # Final balance should be zero or near-zero after last payment.
    assert schedule[-1]["balance"] <= Decimal("0.01")
    total_paid = sum(Decimal(str(row["payment"])) for row in schedule)
    assert total_paid >= Decimal("12000.00")


def test_zero_interest_amortization():
    schedule = compute_amortization_schedule(
        principal=Decimal("1200.00"),
        annual_rate=Decimal("0.00"),
        term_months=6,
        start_date=date(2026, 3, 15),
    )
    assert len(schedule) == 6
    for row in schedule:
        assert row["interest"] == 0.0
        assert row["payment"] == 200.0
        assert row["principal"] == 200.0


# ---------------------------------------------------------------------------
# Loan schedule persistence
# ---------------------------------------------------------------------------

def test_create_loan_schedule_attached_to_account(db: Session):
    user, client, account = _seed_user_and_account(db)
    ls = create_loan_schedule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        original_principal=Decimal("5000.00"),
        annual_rate=Decimal("0.05"),
        term_months=10,
        start_date=date(2026, 4, 1),
    )
    assert ls.id is not None
    assert ls.account_id == account.id
    assert ls.tenant_id == client.id
    assert ls.user_id == user.id
    assert ls.original_principal == Decimal("5000.00")
    assert ls.term_months == 10
    assert ls.payment_amount > 0
    assert ls.schedule_json is not None


def test_loan_schedule_invalid_account(db: Session):
    user, client, _ = _seed_user_and_account(db)
    with pytest.raises(LiabilityError, match="Account not found"):
        create_loan_schedule(
            db=db,
            tenant_id=client.id,
            user_id=user.id,
            account_id=999999,
            original_principal=Decimal("1000.00"),
            annual_rate=Decimal("0.04"),
            term_months=12,
            start_date=date(2026, 1, 1),
        )


# ---------------------------------------------------------------------------
# Credit line tests
# ---------------------------------------------------------------------------

def test_create_credit_line(db: Session):
    user, client, account = _seed_user_and_account(db, account_type="credit_card")
    from backend.accounting.liabilities import create_credit_line
    cl = create_credit_line(
        db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        credit_limit=Decimal("5000.00"), annual_rate=Decimal("0.12"),
        start_date=date(2026, 1, 1),
    )
    assert cl.id is not None
    assert cl.credit_limit == Decimal("5000.00")
    assert cl.current_balance == Decimal("0")


def test_credit_line_draw_and_available(db: Session):
    user, client, account = _seed_user_and_account(db, account_type="credit_card")
    from backend.accounting.liabilities import create_credit_line, credit_line_draw, credit_line_available
    cl = create_credit_line(
        db, tenant_id=client.id, user_id=user.id, account_id=account.id,
        credit_limit=Decimal("5000.00"),
    )
    credit_line_draw(db, cl.id, client.id, user.id, Decimal("2000.00"), date(2026, 1, 15))
    available = credit_line_available(db, cl.id, client.id)
    assert available == Decimal("3000.00")


def test_credit_line_not_found(db: Session):
    from backend.accounting.liabilities import credit_line_available
    with pytest.raises(LiabilityError, match="Credit line not found"):
        credit_line_available(db, credit_line_id=99999, tenant_id=1)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user_has_account(db: Session, account_type="loan"):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Liab Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]

    account = db.query(models.Account).filter(
        models.Account.user_id == auth_user.id,
        models.Account.type == account_type,
    ).first()
    if account is None:
        account = models.Account(
            name=f"Auth {account_type.title()}",
            type=account_type,
            client_id=client.id,
            tenant_id=client.id,
            user_id=auth_user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return auth_user, client, account


def test_api_create_loan_schedule(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db, "loan")
    payload = {
        "account_id": account.id,
        "original_principal": 24000.00,
        "annual_rate": 0.0725,
        "term_months": 24,
        "start_date": "2026-01-01",
    }
    resp = auth_client.post("/api/liabilities/loan-schedule", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["account_id"] == account.id
    assert body["payment_amount"] > 0
    assert len(body["schedule"]) == 24


def test_api_amortization(auth_client: TestClient, db: Session):
    _ensure_auth_user_has_account(db)
    payload = {
        "principal": 10000.00,
        "annual_rate": 0.00,
        "term_months": 5,
        "start_date": "2026-06-01",
    }
    resp = auth_client.post("/api/liabilities/amortization", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 5
    for row in body:
        assert row["payment"] == 2000.00
        assert row["interest"] == 0.0


def test_api_create_credit_line(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db, "credit_card")
    resp = auth_client.post("/api/liabilities/credit-lines", json={
        "account_id": account.id,
        "credit_limit": 5000.00,
        "annual_rate": 0.12,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["credit_limit"] == 5000.00
    assert body["current_balance"] == 0.0


def test_api_credit_line_draw_and_available(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db, "credit_card")
    resp = auth_client.post("/api/liabilities/credit-lines", json={
        "account_id": account.id,
        "credit_limit": 5000.00,
        "annual_rate": 0.0,
    })
    cl_id = resp.json()["id"]
    resp = auth_client.post(f"/api/liabilities/credit-lines/{cl_id}/draw", json={
        "amount": 2000.00,
        "draw_date": "2026-01-15",
    })
    assert resp.status_code == 200, resp.text
    resp = auth_client.get(f"/api/liabilities/credit-lines/{cl_id}/available")
    assert resp.status_code == 200, resp.text
    assert resp.json()["available_credit"] == 3000.00
