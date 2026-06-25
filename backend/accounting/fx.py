"""Multi-currency domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


class FXError(Exception):
    """Domain error for FX operations."""


def set_rate(
    db: Session,
    tenant_id: int,
    user_id: int,
    from_currency: str,
    to_currency: str,
    rate: Decimal,
    effective_date: date,
    source: str = "manual",
) -> models.FXRate:
    """Store a manual FX rate."""
    fx = models.FXRate(
        tenant_id=tenant_id,
        user_id=user_id,
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        rate=rate,
        effective_date=effective_date,
        source=source,
    )
    db.add(fx)
    db.commit()
    db.refresh(fx)
    return fx


def get_rate(
    db: Session,
    tenant_id: int,
    from_currency: str,
    to_currency: str,
    as_of: date | None = None,
) -> Decimal:
    """Return the most recent FX rate for a currency pair, including inverse."""
    query = db.query(models.FXRate).filter(
        models.FXRate.tenant_id == tenant_id,
        models.FXRate.from_currency == from_currency.upper(),
        models.FXRate.to_currency == to_currency.upper(),
    )
    if as_of is not None:
        query = query.filter(models.FXRate.effective_date <= as_of)
    row = query.order_by(models.FXRate.effective_date.desc()).first()
    if row is not None:
        return Decimal(row.rate)

    # Try inverse rate.
    inv_query = db.query(models.FXRate).filter(
        models.FXRate.tenant_id == tenant_id,
        models.FXRate.from_currency == to_currency.upper(),
        models.FXRate.to_currency == from_currency.upper(),
    )
    if as_of is not None:
        inv_query = inv_query.filter(models.FXRate.effective_date <= as_of)
    inv_row = inv_query.order_by(models.FXRate.effective_date.desc()).first()
    if inv_row is None:
        raise FXError("No FX rate found")
    return Decimal("1") / Decimal(inv_row.rate)


def convert(
    db: Session,
    tenant_id: int,
    foreign_amount: Decimal,
    from_currency: str,
    to_currency: str,
    as_of: date | None = None,
) -> Decimal:
    """Convert foreign amount to home currency using stored rate."""
    if from_currency.upper() == to_currency.upper():
        return foreign_amount
    rate = get_rate(db, tenant_id, from_currency, to_currency, as_of)
    return (foreign_amount * rate).quantize(Decimal("0.01"))
