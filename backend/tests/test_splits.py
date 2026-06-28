"""Tests for v3.11.6 B2.02 — Transaction Splits."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.splits import (
    SplitsError,
    validate_splits,
    set_splits,
    get_splits,
    migrate_single_line_to_splits,
    apply_pre_post_allocation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_user_and_account(db: Session):
    """Create user, tenant, account, and COA accounts for split tests."""
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "splitsuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="splitsuser",
        email="splits@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
        encryption_salt="test_salt",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Splits Client", user_id=user.id)
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

    # Create COA accounts
    coa1 = models.CoaAccount(tenant_id=client.id, number=1010, name="Cash", type="asset")
    coa2 = models.CoaAccount(tenant_id=client.id, number=5000, name="Office Supplies", type="expense")
    coa3 = models.CoaAccount(tenant_id=client.id, number=6000, name="Meals", type="expense")
    db.add_all([coa1, coa2, coa3])
    db.commit()
    db.refresh(coa1)
    db.refresh(coa2)
    db.refresh(coa3)

    # Create a synthetic statement for the account
    statement = models.Statement(
        account_id=account.id,
        tenant_id=client.id,
        user_id=user.id,
        filename="__register__",
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    return user, client, account, statement, (coa1, coa2, coa3)


def _create_transaction(db: Session, tenant_id: int, user_id: int, statement_id: int, amount="100.00"):
    """Create a transaction with a given amount."""
    tx = models.Transaction(
        statement_id=statement_id,
        tenant_id=tenant_id,
        user_id=user_id,
        date=date(2026, 6, 1),
        description="Split test tx",
        amount=Decimal(amount),
        tx_type="debit",
        category="test",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_validate_splits_balanced():
    """Splits summing to transaction total should pass."""
    splits = [
        {"account_id": 1, "amount": 60.00},
        {"account_id": 2, "amount": 40.00},
    ]
    result = validate_splits(splits, Decimal("100.00"))
    assert len(result) == 2


def test_validate_splits_unbalanced_rejected():
    """Splits not summing to total should be rejected."""
    splits = [
        {"account_id": 1, "amount": 60.00},
        {"account_id": 2, "amount": 50.00},
    ]
    with pytest.raises(SplitsError, match="does not match transaction total"):
        validate_splits(splits, Decimal("100.00"))


def test_validate_splits_empty_account_rejected():
    """Splits with missing account_id should be rejected."""
    splits = [
        {"account_id": None, "amount": 100.00},
    ]
    with pytest.raises(SplitsError, match="account_id is required"):
        validate_splits(splits, Decimal("100.00"))


def test_validate_splits_zero_amount_rejected():
    """Splits with zero amount should be rejected."""
    splits = [
        {"account_id": 1, "amount": 0},
    ]
    with pytest.raises(SplitsError, match="amount must be non-zero"):
        validate_splits(splits, Decimal("0.00"))


def test_validate_splits_duplicate_rejected():
    """Duplicate splits (same account + amount) should be rejected."""
    splits = [
        {"account_id": 1, "amount": 50.00},
        {"account_id": 1, "amount": 50.00},
    ]
    with pytest.raises(SplitsError, match="duplicate split"):
        validate_splits(splits, Decimal("100.00"))


def test_validate_splits_empty_list_returns_empty():
    """Empty splits list should return empty list."""
    assert validate_splits([], Decimal("100.00")) == []


def test_validate_splits_within_tolerance():
    """Splits within rounding tolerance should pass."""
    splits = [
        {"account_id": 1, "amount": 33.33},
        {"account_id": 2, "amount": 33.33},
        {"account_id": 3, "amount": 33.34},
    ]
    result = validate_splits(splits, Decimal("100.00"))
    assert len(result) == 3


# ---------------------------------------------------------------------------
# Pre/post allocation tests
# ---------------------------------------------------------------------------

def test_pre_post_allocation():
    """Pre/post allocations should be inserted/appended correctly."""
    main_splits = [
        {"account_id": 1, "amount": 80.00},
        {"account_id": 2, "amount": 20.00},
    ]
    pre = {"account_id": 3, "amount": 10.00, "memo": "ATM cash back"}
    post = {"account_id": 4, "amount": 5.00, "memo": "Fee"}

    result = apply_pre_post_allocation(main_splits, pre_allocation=pre, post_allocation=post)
    assert len(result) == 4
    assert result[0]["memo"] == "ATM cash back"
    assert result[-1]["memo"] == "Fee"
    assert result[1]["account_id"] == 1
    assert result[2]["account_id"] == 2


# ---------------------------------------------------------------------------
# Database tests
# ---------------------------------------------------------------------------

def test_set_splits_on_transaction(db: Session):
    """Set splits on a transaction and verify they are stored correctly."""
    user, client, account, statement, coas = _seed_user_and_account(db)
    tx = _create_transaction(db, client.id, user.id, statement.id, "100.00")

    splits = [
        {"account_id": coas[0].id, "amount": 60.00, "memo": "Cash portion"},
        {"account_id": coas[1].id, "amount": 40.00, "memo": "Supplies portion"},
    ]
    updated_tx = set_splits(db, tx.id, client.id, user.id, splits)
    assert updated_tx.splits is not None
    parsed = json.loads(updated_tx.splits)
    assert len(parsed) == 2
    assert parsed[0]["account_id"] == coas[0].id
    assert parsed[1]["account_id"] == coas[1].id


def test_set_splits_unbalanced_rejected(db: Session):
    """Setting unbalanced splits should fail."""
    user, client, account, statement, coas = _seed_user_and_account(db)
    tx = _create_transaction(db, client.id, user.id, statement.id, "100.00")

    splits = [
        {"account_id": coas[0].id, "amount": 70.00},
        {"account_id": coas[1].id, "amount": 40.00},
    ]
    with pytest.raises(SplitsError, match="does not match"):
        set_splits(db, tx.id, client.id, user.id, splits)


def test_set_splits_transaction_not_found(db: Session):
    """Setting splits on a non-existent transaction should fail."""
    with pytest.raises(SplitsError, match="not found"):
        set_splits(db, 999999, 1, 1, [{"account_id": 1, "amount": 100.00}])


def test_get_splits_empty(db: Session):
    """get_splits on a transaction with no splits returns empty list."""
    user, client, account, statement, coas = _seed_user_and_account(db)
    tx = _create_transaction(db, client.id, user.id, statement.id, "100.00")
    assert get_splits(tx) == []


def test_get_splits_after_set(db: Session):
    """get_splits returns the splits after they are set."""
    user, client, account, statement, coas = _seed_user_and_account(db)
    tx = _create_transaction(db, client.id, user.id, statement.id, "100.00")
    splits = [{"account_id": coas[0].id, "amount": 100.00}]
    set_splits(db, tx.id, client.id, user.id, splits)
    result = get_splits(tx)
    assert len(result) == 1
    assert result[0]["account_id"] == coas[0].id


def test_migrate_single_line_to_splits(db: Session):
    """A single-line transaction should be migrated to have a one-entry split."""
    user, client, account, statement, coas = _seed_user_and_account(db)
    tx = _create_transaction(db, client.id, user.id, statement.id, "100.00")
    tx.coa_account_id = coas[0].id
    db.commit()
    db.refresh(tx)

    assert get_splits(tx) == []
    migrate_single_line_to_splits(tx)
    db.commit()
    db.refresh(tx)

    splits = get_splits(tx)
    assert len(splits) == 1
    assert splits[0]["account_id"] == coas[0].id
    assert float(splits[0]["amount"]) == 100.00


def test_migrate_already_has_splits_noop(db: Session):
    """Migrating a transaction that already has splits should be a no-op."""
    user, client, account, statement, coas = _seed_user_and_account(db)
    tx = _create_transaction(db, client.id, user.id, statement.id, "100.00")
    splits = [{"account_id": coas[0].id, "amount": 100.00}]
    set_splits(db, tx.id, client.id, user.id, splits)

    # Migration should not change the existing splits.
    migrate_single_line_to_splits(tx)
    db.commit()
    db.refresh(tx)
    result = get_splits(tx)
    assert len(result) == 1
    assert result[0]["account_id"] == coas[0].id


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Splits Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]

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

    statement = models.Statement(
        account_id=account.id,
        tenant_id=client.id,
        user_id=auth_user.id,
        filename="__register__",
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    coa = models.CoaAccount(
        tenant_id=client.id,
        number=1010,
        name="Cash",
        type="asset",
    )
    db.add(coa)
    db.commit()
    db.refresh(coa)

    tx = models.Transaction(
        statement_id=statement.id,
        tenant_id=client.id,
        user_id=auth_user.id,
        date=date(2026, 6, 1),
        description="API split test",
        amount=Decimal("100.00"),
        tx_type="debit",
        coa_account_id=coa.id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return auth_user, client, account, statement, coa, tx


def test_api_set_splits(auth_client: TestClient, db: Session):
    """Test setting splits via the API."""
    _, _, _, _, coa, tx = _ensure_auth_user(db)

    resp = auth_client.put(
        f"/api/transactions/{tx.id}/splits",
        json={
            "splits": [
                {"account_id": coa.id, "amount": 60.00},
                {"account_id": coa.id, "amount": 40.00},
            ],
        },
    )
    # Duplicate split (same account + different amount is NOT duplicate;
    # same account + same amount IS duplicate). Here amounts differ, so it's OK.
    # Wait — actually the validation checks (account_id, str(amount)) pairs.
    # (coa.id, "60.00") and (coa.id, "40.00") are different pairs, so no duplicate.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["splits"]) == 2


def test_api_set_splits_unbalanced(auth_client: TestClient, db: Session):
    """Test that unbalanced splits are rejected by the API."""
    _, _, _, _, coa, tx = _ensure_auth_user(db)

    resp = auth_client.put(
        f"/api/transactions/{tx.id}/splits",
        json={
            "splits": [
                {"account_id": coa.id, "amount": 70.00},
                {"account_id": coa.id, "amount": 40.00},
            ],
        },
    )
    assert resp.status_code == 400
    assert "does not match" in resp.json()["detail"]


def test_api_get_splits(auth_client: TestClient, db: Session):
    """Test getting splits via the API."""
    _, _, _, _, coa, tx = _ensure_auth_user(db)

    # Set splits first
    auth_client.put(
        f"/api/transactions/{tx.id}/splits",
        json={"splits": [{"account_id": coa.id, "amount": 100.00}]},
    )

    resp = auth_client.get(f"/api/transactions/{tx.id}/splits")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["account_id"] == coa.id


def test_api_migrate_splits(auth_client: TestClient, db: Session):
    """Test migrating a single-line transaction to splits via the API."""
    _, _, _, _, coa, tx = _ensure_auth_user(db)

    resp = auth_client.post(f"/api/transactions/{tx.id}/splits/migrate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["splits"]) == 1
    assert body["splits"][0]["account_id"] == coa.id


def test_api_requires_auth(client: TestClient):
    resp = client.get("/api/transactions/1/splits")
    assert resp.status_code == 401