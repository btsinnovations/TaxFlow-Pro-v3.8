from __future__ import annotations

from typing import Optional
"""Multi-currency domain logic for TaxFlow Pro v3.11.

B3.04 — Full implementation:
- Manual FX rate entry (no live FX API).
- Convert amounts at transaction-date rate or most recent prior rate.
- Inverse rate support.
- Home-currency reporting with FX gain/loss tracking.
- Default home currency = USD.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from .. import models


class FXError(Exception):
    """Domain error for FX operations."""


DEFAULT_HOME_CURRENCY = "USD"


# ---------------------------------------------------------------------------
# Rate management
# ---------------------------------------------------------------------------

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
    if rate <= 0:
        raise FXError("Rate must be positive")
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


def list_rates(
    db: Session,
    tenant_id: int,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> list[models.FXRate]:
    """List FX rates for a tenant, optionally filtered by pair."""
    query = db.query(models.FXRate).filter(
        models.FXRate.tenant_id == tenant_id,
    )
    if from_currency is not None:
        query = query.filter(models.FXRate.from_currency == from_currency.upper())
    if to_currency is not None:
        query = query.filter(models.FXRate.to_currency == to_currency.upper())
    return query.order_by(models.FXRate.effective_date.desc()).all()


def get_rate(
    db: Session,
    tenant_id: int,
    from_currency: str,
    to_currency: str,
    as_of: Optional[date] = None,
) -> Decimal:
    """Return the most recent FX rate for a currency pair, including inverse."""
    if from_currency.upper() == to_currency.upper():
        return Decimal("1")

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
    return (Decimal("1") / Decimal(inv_row.rate)).quantize(Decimal("0.00000001"))


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def convert(
    db: Session,
    tenant_id: int,
    foreign_amount: Decimal,
    from_currency: str,
    to_currency: str,
    as_of: Optional[date] = None,
) -> Decimal:
    """Convert foreign amount to home currency using stored rate."""
    if from_currency.upper() == to_currency.upper():
        return foreign_amount
    rate = get_rate(db, tenant_id, from_currency, to_currency, as_of)
    return (foreign_amount * rate).quantize(Decimal("0.01"))


def convert_with_details(
    db: Session,
    tenant_id: int,
    foreign_amount: Decimal,
    from_currency: str,
    to_currency: str,
    as_of: Optional[date] = None,
) -> dict:
    """Convert and return full details including the rate used."""
    if from_currency.upper() == to_currency.upper():
        return {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "rate": Decimal("1"),
            "amount": foreign_amount,
            "converted": foreign_amount,
            "effective_date": as_of.isoformat() if as_of else None,
        }
    rate = get_rate(db, tenant_id, from_currency, to_currency, as_of)
    converted = (foreign_amount * rate).quantize(Decimal("0.01"))

    # Find the effective date of the rate used
    eff_date = as_of
    if eff_date is None:
        # Find the most recent rate record
        row = db.query(models.FXRate).filter(
            models.FXRate.tenant_id == tenant_id,
            models.FXRate.from_currency == from_currency.upper(),
            models.FXRate.to_currency == to_currency.upper(),
        ).order_by(models.FXRate.effective_date.desc()).first()
        if row is None:
            # Must be inverse
            row = db.query(models.FXRate).filter(
                models.FXRate.tenant_id == tenant_id,
                models.FXRate.from_currency == to_currency.upper(),
                models.FXRate.to_currency == from_currency.upper(),
            ).order_by(models.FXRate.effective_date.desc()).first()
        if row is not None:
            eff_date = row.effective_date

    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "rate": rate,
        "amount": foreign_amount,
        "converted": converted,
        "effective_date": eff_date.isoformat() if eff_date else None,
    }


# ---------------------------------------------------------------------------
# Transaction foreign-currency support
# ---------------------------------------------------------------------------

def attach_foreign_currency(
    db: Session,
    tenant_id: int,
    transaction_id: int,
    foreign_amount: Decimal,
    foreign_currency: str,
) -> models.Transaction:
    """Attach foreign currency info to an existing transaction.

    Computes the home-currency equivalent at the transaction's date rate
    and stores it as the transaction's amount (if not already set differently).
    """
    txn = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.tenant_id == tenant_id,
    ).first()
    if txn is None:
        raise FXError("Transaction not found")

    txn_date = txn.date or date.today()
    rate = get_rate(db, tenant_id, foreign_currency, DEFAULT_HOME_CURRENCY, txn_date)
    home_amount = (foreign_amount * rate).quantize(Decimal("0.01"))

    txn.foreign_amount = foreign_amount
    txn.foreign_currency = foreign_currency.upper()
    txn.fx_rate_snapshot = rate
    # Only set amount if it's not already set
    if txn.amount is None or txn.amount == 0:
        txn.amount = home_amount

    db.commit()
    db.refresh(txn)
    return txn


# ---------------------------------------------------------------------------
# FX gain/loss tracking
# ---------------------------------------------------------------------------

def calculate_fx_gain_loss(
    db: Session,
    tenant_id: int,
    transaction_id: int,
    settlement_date: date,
    settlement_rate: Optional[Decimal] = None,
) -> dict:
    """Calculate FX gain/loss on settlement of a foreign-currency transaction.

    If settlement_rate is not provided, uses the rate at settlement_date.
    Compares the original transaction rate with the settlement rate.
    """
    txn = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.tenant_id == tenant_id,
    ).first()
    if txn is None:
        raise FXError("Transaction not found")
    if txn.foreign_amount is None or txn.foreign_currency is None:
        raise FXError("Transaction has no foreign currency data")

    original_rate = Decimal(str(txn.fx_rate_snapshot)) if txn.fx_rate_snapshot else Decimal("1")
    if settlement_rate is None:
        settlement_rate = get_rate(
            db, tenant_id,
            txn.foreign_currency, DEFAULT_HOME_CURRENCY,
            settlement_date,
        )

    original_home = (Decimal(str(txn.foreign_amount)) * original_rate).quantize(Decimal("0.01"))
    settlement_home = (Decimal(str(txn.foreign_amount)) * settlement_rate).quantize(Decimal("0.01"))
    fx_gain_loss = (settlement_home - original_home).quantize(Decimal("0.01"))

    return {
        "transaction_id": transaction_id,
        "foreign_amount": float(txn.foreign_amount),
        "foreign_currency": txn.foreign_currency,
        "original_rate": float(original_rate),
        "settlement_rate": float(settlement_rate),
        "original_home_amount": float(original_home),
        "settlement_home_amount": float(settlement_home),
        "fx_gain_loss": float(fx_gain_loss),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def home_currency_report(
    db: Session,
    tenant_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    """Generate a home-currency report of all foreign-currency transactions.

    Shows each transaction with its foreign and home amounts, rate used,
    and any FX gain/loss if settled.
    """
    query = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.foreign_currency != None,  # noqa: E711
    )
    if start_date is not None:
        query = query.filter(models.Transaction.date >= start_date)
    if end_date is not None:
        query = query.filter(models.Transaction.date <= end_date)
    txns = query.order_by(models.Transaction.date.desc()).all()

    rows = []
    total_fx_gain = Decimal("0")
    total_fx_loss = Decimal("0")
    for t in txns:
        foreign_amt = Decimal(str(t.foreign_amount)) if t.foreign_amount else Decimal("0")
        rate = Decimal(str(t.fx_rate_snapshot)) if t.fx_rate_snapshot else Decimal("1")
        home_amt = Decimal(str(t.amount)) if t.amount else Decimal("0")
        computed_home = (foreign_amt * rate).quantize(Decimal("0.01"))
        fx_diff = (home_amt - computed_home).quantize(Decimal("0.01"))

        if fx_diff > 0:
            total_fx_gain += fx_diff
        else:
            total_fx_loss += abs(fx_diff)

        rows.append({
            "id": t.id,
            "date": t.date.isoformat() if t.date else None,
            "description": t.description,
            "foreign_amount": float(foreign_amt),
            "foreign_currency": t.foreign_currency,
            "fx_rate": float(rate),
            "home_amount": float(home_amt),
            "fx_gain_loss": float(fx_diff),
        })

    return {
        "home_currency": DEFAULT_HOME_CURRENCY,
        "transactions": rows,
        "total_fx_gain": float(total_fx_gain),
        "total_fx_loss": float(total_fx_loss),
        "net_fx": float(total_fx_gain - total_fx_loss),
    }