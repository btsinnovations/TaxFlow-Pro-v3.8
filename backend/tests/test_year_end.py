"""Tests for year-end closing and tax package (v3.11.6 R4)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.year_end import close_year


def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user is None:
        from backend.routers.auth import get_password_hash
        auth_user = models.User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("T4xFl0…2026"),
            is_active=True,
        )
        db.add(auth_user)
        db.commit()
        db.refresh(auth_user)
    if not auth_user.clients:
        client = models.Client(name="Auth Tax Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def _seed_statement_and_txn(db, account_id, tenant_id, user_id, **kwargs):
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


def test_close_year_creates_adjusting_entries(db: Session):
    user, client = _ensure_auth_user(db)
    # Ensure user id matches the transaction creation logic later.
    sales = create_account(db, client.id, user.id, "4010", "Sales", "income")
    rent = create_account(db, client.id, user.id, "5100", "Rent", "expense")

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
        description="Sale",
        amount=Decimal("2000.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 3, 1),
        description="Rent",
        amount=Decimal("500.00"),
        tx_type="debit",
        coa_account_id=rent["id"],
    )

    # Create a period in 2026 so it gets closed.
    period = models.Period(
        tenant_id=client.id,
        user_id=user.id,
        name="2026-Q1",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    )
    db.add(period)
    db.commit()
    db.refresh(period)

    result = close_year(db, client.id, user.id, 2026)
    assert result["year"] == 2026
    assert result["net_income"] == 1500.0
    assert result["closed_periods"] == 1
    assert result["entries_created"] >= 1

    adjusting = db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == client.id,
        models.GeneralLedgerEntry.entry_type == "adjusting",
    ).all()
    assert len(adjusting) >= 1


def test_api_close_year(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4020", "Service", "income")
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
        date=date(2026, 5, 1),
        description="Service income",
        amount=Decimal("3000.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    resp = auth_client.post("/api/year-end/close", json={"year": 2026})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["year"] == 2026
    assert body["net_income"] == 3000.0
