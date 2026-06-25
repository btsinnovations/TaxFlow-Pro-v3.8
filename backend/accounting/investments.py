"""Investment lot tracking domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


class InvestmentError(Exception):
    """Domain error for investment operations."""


def add_lot(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    symbol: str,
    shares: Decimal,
    cost_basis: Decimal,
    acquisition_date: date,
) -> models.InvestmentLot:
    """Record a purchase lot for an investment account."""
    lot = models.InvestmentLot(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        symbol=symbol.upper(),
        shares=shares,
        cost_basis=cost_basis,
        acquisition_date=acquisition_date,
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot


def sell_lots_fifo(
    db: Session,
    user_id: int,
    account_id: int,
    symbol: str,
    shares_to_sell: Decimal,
    sale_date: date,
    sale_price_per_share: Decimal,
) -> list[dict]:
    """Sell lots using FIFO cost-basis and return realized gain/loss per lot."""
    lots = db.query(models.InvestmentLot).filter(
        models.InvestmentLot.account_id == account_id,
        models.InvestmentLot.user_id == user_id,
        models.InvestmentLot.symbol == symbol.upper(),
        models.InvestmentLot.sale_date == None,
    ).order_by(models.InvestmentLot.acquisition_date).all()

    remaining = shares_to_sell
    results = []
    proceeds_total = Decimal("0.00")
    cost_total = Decimal("0.00")
    for lot in lots:
        if remaining <= 0:
            break
        sell_from_lot = min(lot.shares, remaining)
        lot_proceeds = sell_from_lot * sale_price_per_share
        lot_cost = sell_from_lot * lot.cost_basis
        gain = lot_proceeds - lot_cost
        results.append({
            "lot_id": lot.id,
            "shares_sold": float(sell_from_lot),
            "cost_basis": float(lot.cost_basis),
            "proceeds": float(lot_proceeds),
            "realized_gain": float(gain),
        })
        proceeds_total += lot_proceeds
        cost_total += lot_cost
        lot.shares -= sell_from_lot
        if lot.shares <= 0:
            lot.sale_date = sale_date
            lot.sale_proceeds = lot_proceeds
        remaining -= sell_from_lot
    if remaining > 0:
        raise InvestmentError("Not enough shares to fulfill sale")
    db.commit()
    return results


def holdings(db: Session, user_id: int, account_id: int) -> list[dict]:
    """Return current open holdings grouped by symbol."""
    lots = db.query(models.InvestmentLot).filter(
        models.InvestmentLot.account_id == account_id,
        models.InvestmentLot.user_id == user_id,
        models.InvestmentLot.sale_date == None,
    ).all()
    groups: dict[str, dict] = {}
    for lot in lots:
        g = groups.setdefault(lot.symbol, {"symbol": lot.symbol, "shares": Decimal("0"), "cost_basis": Decimal("0")})
        g["shares"] += lot.shares
        g["cost_basis"] += lot.shares * lot.cost_basis
    return [
        {
            "symbol": g["symbol"],
            "shares": float(g["shares"]),
            "total_cost_basis": float(g["cost_basis"]),
        }
        for g in groups.values()
    ]
