"""Loans / credit lines / liability domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


class LiabilityError(Exception):
    """Domain error for liability operations."""


def compute_amortization_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date,
) -> list[dict]:
    """Compute a standard fixed-payment loan amortization schedule."""
    if term_months <= 0:
        raise LiabilityError("Term must be positive")
    monthly_rate = annual_rate / Decimal("12")
    if monthly_rate == 0:
        payment = principal / term_months
    else:
        payment = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / (
            (1 + monthly_rate) ** term_months - 1
        )
    payment = payment.quantize(Decimal("0.01"))

    schedule = []
    balance = principal
    current_date = start_date
    for month in range(1, term_months + 1):
        interest = (balance * monthly_rate).quantize(Decimal("0.01"))
        principal_paid = (payment - interest).quantize(Decimal("0.01"))
        if principal_paid > balance:
            principal_paid = balance
            payment = (principal_paid + interest).quantize(Decimal("0.01"))
        balance = (balance - principal_paid).quantize(Decimal("0.01"))
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, current_date.day)
        else:
            try:
                current_date = date(current_date.year, current_date.month + 1, current_date.day)
            except ValueError:
                current_date = date(current_date.year, current_date.month + 1, 1)
                current_date = date(current_date.year, current_date.month, 1) - __import__("datetime").timedelta(days=1)
        schedule.append({
            "month": month,
            "date": current_date.isoformat(),
            "payment": float(payment),
            "interest": float(interest),
            "principal": float(principal_paid),
            "balance": float(balance),
        })
        if balance <= 0:
            break
    return schedule


def create_loan_schedule(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    original_principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
    start_date: date,
) -> models.LoanSchedule:
    """Create a loan schedule attached to a liability/credit account."""
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == user_id,
        models.Account.tenant_id == tenant_id,
    ).first()
    if account is None:
        raise LiabilityError("Account not found")
    schedule = compute_amortization_schedule(original_principal, annual_rate, term_months, start_date)
    first_payment = Decimal(str(schedule[0]["payment"])) if schedule else Decimal("0.00")
    ls = models.LoanSchedule(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        original_principal=original_principal,
        rate=annual_rate,
        term_months=term_months,
        start_date=start_date,
        payment_amount=first_payment,
        schedule_json=__import__("json").dumps(schedule),
    )
    db.add(ls)
    db.commit()
    db.refresh(ls)
    return ls


def credit_line_available(db: Session, account_id: int, user_id: int) -> Decimal:
    """Return available credit = limit - current balance (stub)."""
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == user_id,
    ).first()
    if account is None:
        raise LiabilityError("Account not found")
    # Stub: treat account_number_masked as limit string if numeric.
    limit = Decimal("0.00")
    if account.account_number_masked:
        try:
            limit = Decimal(account.account_number_masked.replace("*", ""))
        except Exception:
            pass
    return limit
