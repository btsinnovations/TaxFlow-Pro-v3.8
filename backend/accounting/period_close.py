"""Period close automation for TaxFlow Pro v3.11.6 R2.

Zeroes income/expense accounts and posts net income to Retained Earnings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


RETAINED_EARNINGS_NUMBER = 3100


class PeriodCloseError(Exception):
    """Domain error for period close operations."""


def _get_coa_by_number(db: Session, tenant_id: int, number: int) -> Optional[models.CoaAccount]:
    return db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
        models.CoaAccount.number == number,
    ).first()


def _get_or_create_retained_earnings(db: Session, tenant_id: int) -> models.CoaAccount:
    coa = _get_coa_by_number(db, tenant_id, RETAINED_EARNINGS_NUMBER)
    if coa:
        return coa
    coa = models.CoaAccount(
        tenant_id=tenant_id,
        number=RETAINED_EARNINGS_NUMBER,
        name="Retained Earnings",
        type="equity",
    )
    db.add(coa)
    db.flush()
    return coa


def _gl_balance_for_coa(db: Session, tenant_id: int, coa_account_id: int,
                        start_date, end_date) -> Decimal:
    """Compute the net balance for a COA account from GL entries in the period."""
    debits = db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.debit_coa_account_id == coa_account_id,
        models.GeneralLedgerEntry.date >= start_date,
        models.GeneralLedgerEntry.date <= end_date,
        models.GeneralLedgerEntry.entry_type != "closing",
    ).all()
    credits = db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.credit_coa_account_id == coa_account_id,
        models.GeneralLedgerEntry.date >= start_date,
        models.GeneralLedgerEntry.date <= end_date,
        models.GeneralLedgerEntry.entry_type != "closing",
    ).all()
    total_debits = sum(Decimal(str(e.amount)) for e in debits)
    total_credits = sum(Decimal(str(e.amount)) for e in credits)
    return total_debits - total_credits


def close_period(
    db: Session,
    tenant_id: int,
    user_id: int,
    period_id: int,
    profile_id: Optional[int] = None,
) -> models.Period:
    """Close a period: zero income/expense, post net to Retained Earnings."""
    period = db.query(models.Period).filter(
        models.Period.id == period_id,
        models.Period.tenant_id == tenant_id,
    ).first()
    if period is None:
        raise PeriodCloseError("Period not found")
    if period.is_closed:
        raise PeriodCloseError("Period already closed")

    # Check sequential close — no gaps
    prior_open = db.query(models.Period).filter(
        models.Period.tenant_id == tenant_id,
        models.Period.end_date < period.start_date,
        models.Period.is_closed == False,
    ).first()
    if prior_open:
        raise PeriodCloseError(f"Prior period '{prior_open.name}' must be closed first")

    # Get all income and expense COA accounts
    income_accounts = db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
        models.CoaAccount.type == "income",
    ).all()
    expense_accounts = db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
        models.CoaAccount.type == "expense",
    ).all()

    retained_earnings = _get_or_create_retained_earnings(db, tenant_id)
    closing_date = period.end_date

    total_income = Decimal("0")
    total_expense = Decimal("0")

    # Zero each income account (credit balance → debit to zero)
    for acct in income_accounts:
        balance = _gl_balance_for_coa(db, tenant_id, acct.id, period.start_date, period.end_date)
        # Income has credit balance (negative in debit-credit terms)
        credit_balance = -balance  # positive = credit balance
        if credit_balance != 0:
            entry = models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=closing_date,
                description=f"Closing entry — {acct.name}",
                debit_coa_account_id=acct.id,
                amount=credit_balance,
                memo=f"Period close: {period.name}",
                entry_type="closing",
                source_id=f"period_close:{period_id}",
            )
            db.add(entry)
            total_income += credit_balance

    # Zero each expense account (debit balance → credit to zero)
    for acct in expense_accounts:
        balance = _gl_balance_for_coa(db, tenant_id, acct.id, period.start_date, period.end_date)
        # Expense has debit balance (positive in debit-credit terms)
        debit_balance = balance  # positive = debit balance
        if debit_balance != 0:
            entry = models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=closing_date,
                description=f"Closing entry — {acct.name}",
                credit_coa_account_id=acct.id,
                amount=debit_balance,
                memo=f"Period close: {period.name}",
                entry_type="closing",
                source_id=f"period_close:{period_id}",
            )
            db.add(entry)
            total_expense += debit_balance

    # Post net income to Retained Earnings
    net_income = total_income - total_expense
    if net_income != 0:
        entry = models.GeneralLedgerEntry(
            tenant_id=tenant_id,
            user_id=user_id,
            date=closing_date,
            description=f"Net income to Retained Earnings — {period.name}",
            debit_coa_account_id=retained_earnings.id if net_income < 0 else None,
            credit_coa_account_id=retained_earnings.id if net_income > 0 else None,
            amount=abs(net_income),
            memo=f"Period close: {period.name}",
            entry_type="closing",
            source_id=f"period_close:{period_id}",
        )
        db.add(entry)

    # Mark period closed
    period.is_closed = True
    period.closed_at = datetime.now(timezone.utc)
    period.closed_by_profile_id = profile_id

    db.commit()
    db.refresh(period)
    return period


def reopen_period(
    db: Session,
    tenant_id: int,
    user_id: int,
    period_id: int,
) -> models.Period:
    """Reopen a closed period by deleting closing entries."""
    period = db.query(models.Period).filter(
        models.Period.id == period_id,
        models.Period.tenant_id == tenant_id,
    ).first()
    if period is None:
        raise PeriodCloseError("Period not found")
    if not period.is_closed:
        raise PeriodCloseError("Period is not closed")

    # Check no later period is closed (must reopen in reverse order)
    later_closed = db.query(models.Period).filter(
        models.Period.tenant_id == tenant_id,
        models.Period.start_date > period.start_date,
        models.Period.is_closed == True,
    ).first()
    if later_closed:
        raise PeriodCloseError(f"Later period '{later_closed.name}' is closed — reopen it first")

    # Delete closing entries
    db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.source_id == f"period_close:{period_id}",
    ).delete(synchronize_session=False)

    # Mark period open
    period.is_closed = False
    period.closed_at = None
    period.closed_by_profile_id = None

    db.commit()
    db.refresh(period)
    return period


def get_period_status(db: Session, tenant_id: int, period_id: int) -> dict:
    """Return the close status of a period."""
    period = db.query(models.Period).filter(
        models.Period.id == period_id,
        models.Period.tenant_id == tenant_id,
    ).first()
    if period is None:
        raise PeriodCloseError("Period not found")
    return {
        "id": period.id,
        "name": period.name,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "is_closed": period.is_closed,
        "closed_at": period.closed_at.isoformat() if period.closed_at else None,
        "closed_by_profile_id": period.closed_by_profile_id,
    }


def is_period_closed(db: Session, tenant_id: int, txn_date) -> bool:
    """Check if a date falls within any closed period."""
    if txn_date is None:
        return False
    closed = db.query(models.Period).filter(
        models.Period.tenant_id == tenant_id,
        models.Period.is_closed == True,
        models.Period.start_date <= txn_date,
        models.Period.end_date >= txn_date,
    ).first()
    return closed is not None