from __future__ import annotations

from typing import Optional
"""Loans / credit lines / liability domain logic for TaxFlow Pro v3.11.

B3.01 — Full implementation:
- Amortization schedules (fixed payment, principal + interest breakdown).
- Loan payment tracking with principal/interest allocation.
- Credit line: limit, balance, simple interest accrual, draws, payments.
- Generate upcoming payment transactions from amortization schedule.
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from .. import models


class LiabilityError(Exception):
    """Domain error for liability operations."""


# ---------------------------------------------------------------------------
# Amortization schedule computation
# ---------------------------------------------------------------------------

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
        # Advance one month
        if current_date.month == 12:
            next_date = date(current_date.year + 1, 1, current_date.day)
        else:
            try:
                next_date = date(current_date.year, current_date.month + 1, current_date.day)
            except ValueError:
                # Handle day overflow (e.g., Jan 31 -> Feb 28)
                next_month = current_date.month + 1
                next_year = current_date.year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                # Use last valid day of the month
                if next_month == 12:
                    next_date = date(next_year, 12, 31)
                else:
                    next_date = date(next_year, next_month, 1) - timedelta(days=1)
        schedule.append({
            "month": month,
            "date": next_date.isoformat(),
            "payment": float(payment),
            "interest": float(interest),
            "principal": float(principal_paid),
            "balance": float(balance),
        })
        current_date = next_date
        if balance <= 0:
            break
    return schedule


# ---------------------------------------------------------------------------
# Loan schedule CRUD
# ---------------------------------------------------------------------------

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
        schedule_json=json.dumps(schedule),
    )
    db.add(ls)
    db.commit()
    db.refresh(ls)
    return ls


def get_loan_schedule(db: Session, schedule_id: int, tenant_id: int) -> models.LoanSchedule:
    """Get a loan schedule by ID, scoped to tenant."""
    ls = db.query(models.LoanSchedule).filter(
        models.LoanSchedule.id == schedule_id,
        models.LoanSchedule.tenant_id == tenant_id,
    ).first()
    if ls is None:
        raise LiabilityError("Loan schedule not found")
    return ls


def list_loan_schedules(db: Session, tenant_id: int) -> list[models.LoanSchedule]:
    """List all loan schedules for a tenant."""
    return db.query(models.LoanSchedule).filter(
        models.LoanSchedule.tenant_id == tenant_id,
    ).order_by(models.LoanSchedule.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Loan payment tracking
# ---------------------------------------------------------------------------

def record_loan_payment(
    db: Session,
    schedule_id: int,
    tenant_id: int,
    user_id: int,
    payment_date: date,
    payment_amount: Decimal,
) -> models.LoanPayment:
    """Record a loan payment, allocating to principal/interest.

    Uses the amortization schedule to determine the split. If the payment
    doesn't match the scheduled amount, we still allocate based on the
    current period's interest due.
    """
    ls = get_loan_schedule(db, schedule_id, tenant_id)
    schedule = json.loads(ls.schedule_json or "[]")
    if not schedule:
        raise LiabilityError("Schedule is empty")

    # Determine the current period based on payments already made.
    existing_payments = db.query(models.LoanPayment).filter(
        models.LoanPayment.schedule_id == schedule_id,
    ).order_by(models.LoanPayment.payment_date).all()

    period_index = len(existing_payments)
    if period_index >= len(schedule):
        raise LiabilityError("All payments already recorded")

    current_period = schedule[period_index]
    scheduled_interest = Decimal(str(current_period["interest"]))
    scheduled_principal = Decimal(str(current_period["principal"]))

    # Allocate payment: interest first, then principal
    interest_paid = min(payment_amount, scheduled_interest)
    principal_paid = payment_amount - interest_paid

    # Calculate remaining principal
    total_principal_paid = sum(Decimal(str(p.principal_paid)) for p in existing_payments)
    remaining_principal = Decimal(str(ls.original_principal)) - total_principal_paid - principal_paid

    payment = models.LoanPayment(
        schedule_id=schedule_id,
        tenant_id=tenant_id,
        user_id=user_id,
        payment_date=payment_date,
        payment_amount=payment_amount,
        principal_paid=principal_paid,
        interest_paid=interest_paid,
        remaining_principal=remaining_principal,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def list_loan_payments(db: Session, schedule_id: int, tenant_id: int) -> list[models.LoanPayment]:
    """List all payments for a loan schedule."""
    return db.query(models.LoanPayment).filter(
        models.LoanPayment.schedule_id == schedule_id,
        models.LoanPayment.tenant_id == tenant_id,
    ).order_by(models.LoanPayment.payment_date).all()


def generate_upcoming_payments(
    db: Session,
    schedule_id: int,
    tenant_id: int,
    months_ahead: int = 3,
) -> list[dict]:
    """Generate upcoming payment transactions from the amortization schedule.

    Returns a list of payment dicts for the next N unpaid periods.
    """
    ls = get_loan_schedule(db, schedule_id, tenant_id)
    schedule = json.loads(ls.schedule_json or "[]")
    existing_count = db.query(models.LoanPayment).filter(
        models.LoanPayment.schedule_id == schedule_id,
    ).count()

    upcoming = []
    for i in range(existing_count, min(existing_count + months_ahead, len(schedule))):
        period = schedule[i]
        upcoming.append({
            "month": period["month"],
            "date": period["date"],
            "payment_amount": period["payment"],
            "interest": period["interest"],
            "principal": period["principal"],
            "balance": period["balance"],
        })
    return upcoming


# ---------------------------------------------------------------------------
# Credit line management
# ---------------------------------------------------------------------------

def create_credit_line(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    credit_limit: Decimal,
    annual_rate: Decimal = Decimal("0"),
    start_date: Optional[date] = None,
) -> models.CreditLine:
    """Create a revolving credit line attached to an account."""
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == user_id,
        models.Account.tenant_id == tenant_id,
    ).first()
    if account is None:
        raise LiabilityError("Account not found")
    cl = models.CreditLine(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        credit_limit=credit_limit,
        current_balance=Decimal("0"),
        annual_rate=annual_rate,
        last_interest_date=start_date,
    )
    db.add(cl)
    db.commit()
    db.refresh(cl)
    return cl


def credit_line_draw(
    db: Session,
    credit_line_id: int,
    tenant_id: int,
    user_id: int,
    amount: Decimal,
    draw_date: date,
) -> models.CreditLineTransaction:
    """Draw on a credit line. Increases balance."""
    cl = db.query(models.CreditLine).filter(
        models.CreditLine.id == credit_line_id,
        models.CreditLine.tenant_id == tenant_id,
    ).first()
    if cl is None:
        raise LiabilityError("Credit line not found")

    # Accrue interest first
    _accrue_interest(db, cl, draw_date)

    if cl.current_balance + amount > cl.credit_limit:
        raise LiabilityError("Draw exceeds available credit")

    cl.current_balance += amount

    txn = models.CreditLineTransaction(
        credit_line_id=credit_line_id,
        date=draw_date,
        amount=amount,
        type="draw",
        interest_charge=Decimal("0"),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def credit_line_payment(
    db: Session,
    credit_line_id: int,
    tenant_id: int,
    user_id: int,
    amount: Decimal,
    payment_date: date,
) -> models.CreditLineTransaction:
    """Make a payment on a credit line. Decreases balance."""
    cl = db.query(models.CreditLine).filter(
        models.CreditLine.id == credit_line_id,
        models.CreditLine.tenant_id == tenant_id,
    ).first()
    if cl is None:
        raise LiabilityError("Credit line not found")

    # Accrue interest first
    interest = _accrue_interest(db, cl, payment_date)

    if amount > cl.current_balance:
        raise LiabilityError("Payment exceeds current balance")

    cl.current_balance -= amount

    txn = models.CreditLineTransaction(
        credit_line_id=credit_line_id,
        date=payment_date,
        amount=-amount,
        type="payment",
        interest_charge=interest,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def credit_line_available(db: Session, credit_line_id: int, tenant_id: int) -> Decimal:
    """Return available credit = limit - current balance."""
    cl = db.query(models.CreditLine).filter(
        models.CreditLine.id == credit_line_id,
        models.CreditLine.tenant_id == tenant_id,
    ).first()
    if cl is None:
        raise LiabilityError("Credit line not found")
    return cl.credit_limit - cl.current_balance


def _accrue_interest(db: Session, cl: models.CreditLine, as_of: date) -> Decimal:
    """Accrue simple daily interest on the credit line balance.

    Returns the interest amount charged in this accrual period.
    """
    if cl.last_interest_date is None:
        cl.last_interest_date = as_of
        return Decimal("0")

    if cl.annual_rate == 0 or cl.current_balance == 0:
        cl.last_interest_date = as_of
        return Decimal("0")

    days = (as_of - cl.last_interest_date).days
    if days <= 0:
        return Decimal("0")

    daily_rate = cl.annual_rate / Decimal("365")
    interest = (cl.current_balance * daily_rate * Decimal(days)).quantize(Decimal("0.01"))
    cl.current_balance += interest
    cl.last_interest_date = as_of
    return interest


def list_credit_lines(db: Session, tenant_id: int) -> list[models.CreditLine]:
    """List all credit lines for a tenant."""
    return db.query(models.CreditLine).filter(
        models.CreditLine.tenant_id == tenant_id,
    ).order_by(models.CreditLine.created_at.desc()).all()


def get_credit_line(db: Session, credit_line_id: int, tenant_id: int) -> models.CreditLine:
    """Get a credit line by ID, scoped to tenant."""
    cl = db.query(models.CreditLine).filter(
        models.CreditLine.id == credit_line_id,
        models.CreditLine.tenant_id == tenant_id,
    ).first()
    if cl is None:
        raise LiabilityError("Credit line not found")
    return cl


def list_credit_line_transactions(
    db: Session, credit_line_id: int, tenant_id: int
) -> list[models.CreditLineTransaction]:
    """List all transactions for a credit line."""
    return db.query(models.CreditLineTransaction).filter(
        models.CreditLineTransaction.credit_line_id == credit_line_id,
    ).order_by(models.CreditLineTransaction.date).all()