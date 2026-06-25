"""Tests for the v3.11 Investments module (FIFO lots + holdings)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.investments import InvestmentError, add_lot, holdings, sell_lots_fifo


def _seed_user_and_account(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "invuser").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="invuser",
        email="inv@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Inv Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)

    account = models.Account(
        name="Investment Account",
        type="investment",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return user, client, account


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------

def test_add_lot(db: Session):
    user, client, account = _seed_user_and_account(db)
    lot = add_lot(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        account_id=account.id,
        symbol="AAPL",
        shares=Decimal("10.5"),
        cost_basis=Decimal("150.0000"),
        acquisition_date=date(2025, 6, 1),
    )
    assert lot.id is not None
    assert lot.symbol == "AAPL"
    assert lot.shares == Decimal("10.5")
    assert lot.cost_basis == Decimal("150.0000")
    assert lot.account_id == account.id


def test_holdings_grouped_by_symbol(db: Session):
    user, client, account = _seed_user_and_account(db)
    add_lot(db, client.id, user.id, account.id, "TSLA", Decimal("5"), Decimal("200.00"), date(2025, 1, 1))
    add_lot(db, client.id, user.id, account.id, "TSLA", Decimal("3"), Decimal("220.00"), date(2025, 2, 1))
    add_lot(db, client.id, user.id, account.id, "NVDA", Decimal("2"), Decimal("100.00"), date(2025, 1, 15))

    result = holdings(db, user_id=user.id, account_id=account.id)
    assert len(result) == 2
    by_symbol = {row["symbol"]: row for row in result}

    assert by_symbol["TSLA"]["shares"] == 8.0
    assert by_symbol["TSLA"]["total_cost_basis"] == pytest.approx(1660.00, abs=0.01)

    assert by_symbol["NVDA"]["shares"] == 2.0
    assert by_symbol["NVDA"]["total_cost_basis"] == 200.00


def test_sell_lots_fifo_partial(db: Session):
    user, client, account = _seed_user_and_account(db)
    lot = add_lot(db, client.id, user.id, account.id, "AAPL", Decimal("10"), Decimal("100.00"), date(2025, 1, 1))
    result = sell_lots_fifo(
        db,
        user_id=user.id,
        account_id=account.id,
        symbol="AAPL",
        shares_to_sell=Decimal("3"),
        sale_date=date(2026, 1, 1),
        sale_price_per_share=Decimal("150.00"),
    )
    assert len(result) == 1
    assert result[0]["lot_id"] == lot.id
    assert result[0]["shares_sold"] == 3.0
    assert result[0]["realized_gain"] == 150.00  # 3 * (150 - 100)

    remaining = db.query(models.InvestmentLot).filter(models.InvestmentLot.id == lot.id).first()
    assert remaining.shares == Decimal("7")
    assert remaining.sale_date is None


def test_sell_lots_fifo_multiple(db: Session):
    user, client, account = _seed_user_and_account(db)
    lot1 = add_lot(db, client.id, user.id, account.id, "AAPL", Decimal("5"), Decimal("100.00"), date(2025, 1, 1))
    lot2 = add_lot(db, client.id, user.id, account.id, "AAPL", Decimal("5"), Decimal("120.00"), date(2025, 3, 1))

    result = sell_lots_fifo(
        db,
        user_id=user.id,
        account_id=account.id,
        symbol="AAPL",
        shares_to_sell=Decimal("8"),
        sale_date=date(2026, 1, 1),
        sale_price_per_share=Decimal("150.00"),
    )
    assert len(result) == 2
    assert result[0]["lot_id"] == lot1.id
    assert result[0]["shares_sold"] == 5.0
    assert result[0]["realized_gain"] == 250.00  # 5 * (150 - 100)
    assert result[1]["lot_id"] == lot2.id
    assert result[1]["shares_sold"] == 3.0
    assert result[1]["realized_gain"] == 90.00  # 3 * (150 - 120)

    lot1_after = db.query(models.InvestmentLot).filter(models.InvestmentLot.id == lot1.id).first()
    lot2_after = db.query(models.InvestmentLot).filter(models.InvestmentLot.id == lot2.id).first()
    assert lot1_after.shares == Decimal("0")
    assert lot1_after.sale_date is not None
    assert lot2_after.shares == Decimal("2")
    assert lot2_after.sale_date is None


def test_sell_lots_fifo_over_sell(db: Session):
    user, client, account = _seed_user_and_account(db)
    add_lot(db, client.id, user.id, account.id, "AAPL", Decimal("2"), Decimal("100.00"), date(2025, 1, 1))
    with pytest.raises(InvestmentError, match="Not enough shares"):
        sell_lots_fifo(
            db,
            user_id=user.id,
            account_id=account.id,
            symbol="AAPL",
            shares_to_sell=Decimal("5"),
            sale_date=date(2026, 1, 1),
            sale_price_per_share=Decimal("150.00"),
        )


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user_has_account(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Inv Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]

    account = db.query(models.Account).filter(
        models.Account.user_id == auth_user.id,
        models.Account.type == "investment",
    ).first()
    if account is None:
        account = models.Account(
            name="Auth Investment",
            type="investment",
            client_id=client.id,
            tenant_id=client.id,
            user_id=auth_user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return auth_user, client, account


def test_api_add_lot(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db)
    payload = {
        "account_id": account.id,
        "symbol": "MSFT",
        "shares": 10.0,
        "cost_basis": 300.0,
        "acquisition_date": "2025-07-01",
    }
    resp = auth_client.post("/api/investments/lots", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["symbol"] == "MSFT"
    assert body["shares"] == 10.0
    assert body["cost_basis"] == 300.0


def test_api_get_holdings(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db)
    add_lot(db, account.tenant_id, account.user_id, account.id, "AMZN", Decimal("4"), Decimal("125.00"), date(2025, 4, 1))
    add_lot(db, account.tenant_id, account.user_id, account.id, "AMZN", Decimal("6"), Decimal("135.00"), date(2025, 5, 1))
    resp = auth_client.get(f"/api/investments/{account.id}/holdings")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["symbol"] == "AMZN"
    assert body[0]["shares"] == 10.0
    assert body[0]["total_cost_basis"] == pytest.approx(1310.00, abs=0.01)


def test_api_sell_lots(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db)
    add_lot(db, account.tenant_id, account.user_id, account.id, "GOOG", Decimal("10"), Decimal("100.00"), date(2025, 1, 1))
    payload = {
        "symbol": "GOOG",
        "shares": 4.0,
        "sale_date": "2026-01-01",
        "sale_price_per_share": 150.0,
    }
    resp = auth_client.post(f"/api/investments/{account.id}/sell", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["shares_sold"] == 4.0
    assert body[0]["realized_gain"] == 200.00


def test_api_sell_lots_over_sell(auth_client: TestClient, db: Session):
    _, _, account = _ensure_auth_user_has_account(db)
    add_lot(db, account.tenant_id, account.user_id, account.id, "META", Decimal("2"), Decimal("100.00"), date(2025, 1, 1))
    payload = {
        "symbol": "META",
        "shares": 5.0,
        "sale_date": "2026-01-01",
        "sale_price_per_share": 200.0,
    }
    resp = auth_client.post(f"/api/investments/{account.id}/sell", json=payload)
    assert resp.status_code == 400
    assert "Not enough shares" in resp.json()["detail"]
