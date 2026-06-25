"""Tests for the v3.11 FX (multi-currency) module."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.fx import FXError, convert, set_rate


def _seed_user_and_tenant(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "fxuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="fxuser",
        email="fx@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="FX Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------

def test_set_rate(db: Session):
    user, client = _seed_user_and_tenant(db)
    fx = set_rate(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        from_currency="USD",
        to_currency="CAD",
        rate=Decimal("1.35"),
        effective_date=date(2026, 1, 1),
    )
    assert fx.id is not None
    assert fx.from_currency == "USD"
    assert fx.to_currency == "CAD"
    assert fx.rate == Decimal("1.35")
    assert fx.tenant_id == client.id


def test_convert_uses_latest_rate(db: Session):
    user, client = _seed_user_and_tenant(db)
    set_rate(db, client.id, user.id, "USD", "CAD", Decimal("1.35"), date(2026, 1, 1))
    result = convert(db, client.id, Decimal("100.00"), "USD", "CAD")
    assert result == Decimal("135.00")


def test_convert_inverse_rate(db: Session):
    user, client = _seed_user_and_tenant(db)
    set_rate(db, client.id, user.id, "USD", "CAD", Decimal("1.25"), date(2026, 1, 1))
    result = convert(db, client.id, Decimal("125.00"), "CAD", "USD")
    assert result == Decimal("100.00")


def test_convert_missing_rate_fails(db: Session):
    user, client = _seed_user_and_tenant(db)
    with pytest.raises(FXError, match="No FX rate found"):
        convert(db, client.id, Decimal("100.00"), "EUR", "JPY")


def test_convert_uses_closest_prior_rate(db: Session):
    user, client = _seed_user_and_tenant(db)
    set_rate(db, client.id, user.id, "USD", "CAD", Decimal("1.30"), date(2026, 1, 1))
    set_rate(db, client.id, user.id, "USD", "CAD", Decimal("1.40"), date(2026, 6, 1))
    result = convert(db, client.id, Decimal("100.00"), "USD", "CAD", as_of=date(2026, 3, 1))
    assert result == Decimal("130.00")


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth FX Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    return auth_user, auth_user.clients[0]


def test_api_set_rate(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "from_currency": "USD",
        "to_currency": "EUR",
        "rate": 0.92,
        "effective_date": "2026-01-01",
    }
    resp = auth_client.post("/api/fx/rates", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["from_currency"] == "USD"
    assert body["to_currency"] == "EUR"
    assert body["rate"] == 0.92


def test_api_convert(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    set_rate(db, client.id, auth_user.id, "USD", "GBP", Decimal("0.80"), date(2026, 1, 1))
    payload = {
        "amount": 500.0,
        "from_currency": "USD",
        "to_currency": "GBP",
        "as_of": "2026-01-15",
    }
    resp = auth_client.post("/api/fx/convert", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["converted"] == 400.0


def test_api_convert_missing_rate(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "amount": 100.0,
        "from_currency": "AUD",
        "to_currency": "NZD",
    }
    resp = auth_client.post("/api/fx/convert", json=payload)
    assert resp.status_code == 404
    assert "No FX rate found" in resp.json()["detail"]
