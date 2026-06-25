"""Tests for the v3.11 Recurring / Scheduled Transactions module."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.recurring import (
    RecurringRule,
    _advance_date,
    create_rule,
    generate_upcoming,
    get_rule,
    list_rules,
    materialize_rule,
    update_rule,
)


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def _make_user_and_account(db: Session):
    from backend.routers.auth import get_password_hash

    existing = db.query(models.User).filter(models.User.username == "recurringuser").first()
    if existing:
        db.delete(existing)
        db.commit()

    user = models.User(
        username="recurringuser",
        email="recurring@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Recurring Client", user_id=user.id)
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

    # Seed a COA account so account lookup / validation logic can resolve.
    coa = models.GLAccount(
        tenant_id=client.id,
        user_id=user.id,
        code="1000",
        name="Checking",
        account_type="asset",
    )
    db.add(coa)
    db.commit()

    return user, client, account


# ---------------------------------------------------------------------------
# Unit tests for date arithmetic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start,frequency,expected",
    [
        (date(2026, 1, 1), "daily", date(2026, 1, 2)),
        (date(2026, 1, 1), "weekly", date(2026, 1, 8)),
        (date(2026, 1, 31), "monthly", date(2026, 2, 28)),
        (date(2026, 12, 31), "monthly", date(2027, 1, 31)),
        (date(2026, 6, 15), "yearly", date(2027, 6, 15)),
    ],
)
def test_advance_date(start, frequency, expected):
    assert _advance_date(start, frequency) == expected


def test_generate_upcoming_monthly():
    rule = RecurringRule(
        id=1,
        account_id=10,
        tenant_id=20,
        user_id=30,
        amount=Decimal("100.00"),
        description="Monthly subscription",
        frequency="monthly",
        start_date=date(2026, 1, 1),
        next_date=date(2026, 1, 1),
        is_active=True,
    )
    dates = generate_upcoming(rule, count=3)
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_generate_upcoming_inactive_rule():
    rule = RecurringRule(
        id=1,
        account_id=10,
        tenant_id=20,
        user_id=30,
        amount=Decimal("100.00"),
        description="Monthly subscription",
        frequency="monthly",
        start_date=date(2026, 1, 1),
        is_active=False,
    )
    assert generate_upcoming(rule, count=3) == []


def test_generate_upcoming_respects_end_date():
    rule = RecurringRule(
        id=1,
        account_id=10,
        tenant_id=20,
        user_id=30,
        amount=Decimal("100.00"),
        description="Monthly subscription",
        frequency="monthly",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 15),
        is_active=True,
    )
    dates = generate_upcoming(rule, count=5)
    assert dates == [date(2026, 1, 1), date(2026, 2, 1)]


def test_generate_upcoming_respects_count():
    rule = RecurringRule(
        id=1,
        account_id=10,
        tenant_id=20,
        user_id=30,
        amount=Decimal("100.00"),
        description="Limited subscription",
        frequency="monthly",
        start_date=date(2026, 1, 1),
        count=2,
        is_active=True,
    )
    dates = generate_upcoming(rule, count=5)
    assert dates == [date(2026, 1, 1), date(2026, 2, 1)]


# ---------------------------------------------------------------------------
# Domain logic tests with database
# ---------------------------------------------------------------------------

def test_create_rule(db: Session):
    user, client, account = _make_user_and_account(db)
    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="Rent",
        amount="1200.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    assert rule.id is not None
    assert rule.description == "Rent"
    assert rule.amount == Decimal("1200.00")
    assert rule.frequency == "monthly"
    assert rule.next_date == date(2026, 1, 1)
    assert rule.tenant_id == client.id


def test_create_rule_rejects_invalid_frequency(db: Session):
    user, client, account = _make_user_and_account(db)
    with pytest.raises(Exception) as exc_info:
        create_rule(
            db=db,
            tenant_id=client.id,
            user_id=user.id,
            account_id=account.id,
            description="Rent",
            amount=100,
            frequency="hourly",
            start_date=date(2026, 1, 1),
        )
    assert "Invalid frequency" in str(exc_info.value)


def test_update_rule(db: Session):
    user, client, account = _make_user_and_account(db)
    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="Rent",
        amount="1200.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    updated = update_rule(
        db=db,
        rule_id=rule.id,
        tenant_id=client.id,
        user_id=user.id,
        amount="1250.00",
        description="Rent updated",
    )
    assert updated.amount == Decimal("1250.00")
    assert updated.description == "Rent updated"
    assert updated.frequency == "monthly"


def test_delete_rule(db: Session):
    user, client, account = _make_user_and_account(db)
    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="Rent",
        amount="1200.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    from backend.accounting.recurring import delete_rule as _delete

    _delete(db=db, rule_id=rule.id, tenant_id=client.id, user_id=user.id)
    assert get_rule(db, rule.id, tenant_id=client.id, user_id=user.id) is None


# ---------------------------------------------------------------------------
# Materialization tests
# ---------------------------------------------------------------------------

def test_materialize_rule_creates_transactions(db: Session):
    user, client, account = _make_user_and_account(db)
    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="Rent",
        amount="1200.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    created = materialize_rule(db, rule.id, as_of_date=date(2026, 3, 31))
    assert len(created) == 3
    descriptions = {t["description"] for t in created}
    assert descriptions == {"Rent"}

    model_rule = db.query(models.RecurringRule).filter(models.RecurringRule.id == rule.id).first()
    assert model_rule.next_date == date(2026, 4, 1)


def test_materialize_rule_respects_count(db: Session):
    user, client, account = _make_user_and_account(db)
    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="Limited",
        amount="100.00",
        frequency="weekly",
        start_date=date(2026, 1, 1),
        count=2,
    )
    created = materialize_rule(db, rule.id, as_of_date=date(2026, 12, 31))
    assert len(created) == 2


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def test_api_list_recurring(auth_client: TestClient, db: Session):
    user, client, account = _make_user_and_account(db)
    # Ensure the auth_client user has a primary client so tenant resolution matches.
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user and not auth_user.clients:
        auth_client_obj = models.Client(name="Auth Test Client", user_id=auth_user.id)
        db.add(auth_client_obj)
        db.commit()
        db.refresh(auth_client_obj)
        auth_account = models.Account(
            name="Auth Checking",
            type="checking",
            client_id=auth_client_obj.id,
            tenant_id=auth_client_obj.id,
            user_id=auth_user.id,
        )
        db.add(auth_account)
        db.commit()
        db.refresh(auth_account)
        # Replace test account with auth-owned account.
        account = auth_account
        client = auth_client_obj

    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=auth_user.id,
        account_id=account.id,
        description="API rule",
        amount="50.00",
        frequency="weekly",
        start_date=date(2026, 1, 1),
    )
    resp = auth_client.get("/api/recurring")
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["id"] == rule.id for r in data)


def test_api_create_recurring(auth_client: TestClient, db: Session):
    user, client, account = _make_user_and_account(db)
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user and not auth_user.clients:
        auth_client_obj = models.Client(name="Auth Test Client", user_id=auth_user.id)
        db.add(auth_client_obj)
        db.commit()
        db.refresh(auth_client_obj)
        auth_account = models.Account(
            name="Auth Checking",
            type="checking",
            client_id=auth_client_obj.id,
            tenant_id=auth_client_obj.id,
            user_id=auth_user.id,
        )
        db.add(auth_account)
        db.commit()
        db.refresh(auth_account)
        account = auth_account
        client = auth_client_obj
        user = auth_user

    payload = {
        "account_id": account.id,
        "description": "New recurring",
        "amount": 75.0,
        "frequency": "monthly",
        "start_date": "2026-01-01",
    }
    resp = auth_client.post("/api/recurring", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["description"] == "New recurring"
    assert data["frequency"] == "monthly"
    assert data["amount"] == 75.0


def test_api_update_recurring(auth_client: TestClient, db: Session):
    user, client, account = _make_user_and_account(db)
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user and not auth_user.clients:
        auth_client_obj = models.Client(name="Auth Test Client", user_id=auth_user.id)
        db.add(auth_client_obj)
        db.commit()
        db.refresh(auth_client_obj)
        auth_account = models.Account(
            name="Auth Checking",
            type="checking",
            client_id=auth_client_obj.id,
            tenant_id=auth_client_obj.id,
            user_id=auth_user.id,
        )
        db.add(auth_account)
        db.commit()
        db.refresh(auth_account)
        account = auth_account
        client = auth_client_obj
        user = auth_user

    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="Original",
        amount="100.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    resp = auth_client.put(
        f"/api/recurring/{rule.id}",
        json={"description": "Updated", "amount": 200.0},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["description"] == "Updated"
    assert data["amount"] == 200.0


def test_api_delete_recurring(auth_client: TestClient, db: Session):
    user, client, account = _make_user_and_account(db)
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user and not auth_user.clients:
        auth_client_obj = models.Client(name="Auth Test Client", user_id=auth_user.id)
        db.add(auth_client_obj)
        db.commit()
        db.refresh(auth_client_obj)
        auth_account = models.Account(
            name="Auth Checking",
            type="checking",
            client_id=auth_client_obj.id,
            tenant_id=auth_client_obj.id,
            user_id=auth_user.id,
        )
        db.add(auth_account)
        db.commit()
        db.refresh(auth_account)
        account = auth_account
        client = auth_client_obj
        user = auth_user

    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="To delete",
        amount="100.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    resp = auth_client.delete(f"/api/recurring/{rule.id}")
    assert resp.status_code == 200
    assert get_rule(db, rule.id, tenant_id=client.id, user_id=user.id) is None


def test_api_materialize_recurring(auth_client: TestClient, db: Session):
    user, client, account = _make_user_and_account(db)
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user and not auth_user.clients:
        auth_client_obj = models.Client(name="Auth Test Client", user_id=auth_user.id)
        db.add(auth_client_obj)
        db.commit()
        db.refresh(auth_client_obj)
        auth_account = models.Account(
            name="Auth Checking",
            type="checking",
            client_id=auth_client_obj.id,
            tenant_id=auth_client_obj.id,
            user_id=auth_user.id,
        )
        db.add(auth_account)
        db.commit()
        db.refresh(auth_account)
        account = auth_account
        client = auth_client_obj
        user = auth_user

    rule = create_rule(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        description="API materialize",
        amount="100.00",
        frequency="monthly",
        start_date=date(2026, 1, 1),
    )
    resp = auth_client.post(f"/api/recurring/{rule.id}/materialize?as_of=2026-03-31")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["materialized"] == 3


def test_scheduler_stub():
    from backend.local.scheduler import schedule_recurring_check

    result = schedule_recurring_check()
    assert result["ok"] is True
    assert result["mode"] == "offline"
    assert "checked_at" in result
