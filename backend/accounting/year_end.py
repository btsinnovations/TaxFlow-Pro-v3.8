"""Year-end closing and tax-package generation for TaxFlow Pro v3.11.6."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.accounting.reports import profit_and_loss
from backend.accounting.tax_exports import schedule_c


RETAINED_EARNINGS_NUMBER = 3100
INCOME_SUMMARY_NUMBER = 3999


def _get_or_create_coa(
    db: Session,
    tenant_id: int,
    number: int,
    name: str,
    account_type: str,
) -> models.CoaAccount:
    existing = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.tenant_id == tenant_id,
            models.CoaAccount.number == number,
        )
        .first()
    )
    if existing:
        return existing
    account = models.CoaAccount(
        tenant_id=tenant_id,
        number=number,
        name=name,
        type=account_type,
    )
    db.add(account)
    db.flush()
    return account


def _coa_balance(
    db: Session,
    account_id: int,
    start_date: date,
    end_date: date,
) -> Decimal:
    """Return signed balance for an account in the period.

    Uses the same sign convention as profit_and_loss: credits positive for
    income, debits positive for expenses.
    """
    total = Decimal("0")
    for t in (
        db.query(models.Transaction)
        .filter(
            models.Transaction.coa_account_id == account_id,
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
        )
        .all()
    ):
        tx_type = (t.tx_type or "").lower()
        amt = Decimal(str(t.amount or 0))
        if tx_type in ("credit", "deposit", "income"):
            total += amt
        else:
            total -= amt
    return total


def close_year(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
) -> dict:
    """Run a simplified year-end close for the tenant.

    Creates closing GL entries that zero out income and expense COA accounts
    for the year and move the net result into Retained Earnings. Also marks
    every period that falls within the year as closed.
    """
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    # Ensure retained earnings and income summary accounts exist.
    retained_earnings = _get_or_create_coa(
        db, tenant_id, RETAINED_EARNINGS_NUMBER, "Retained Earnings", "equity"
    )
    income_summary = _get_or_create_coa(
        db, tenant_id, INCOME_SUMMARY_NUMBER, "Income Summary", "equity"
    )

    accounts = (
        db.query(models.CoaAccount)
        .filter(models.CoaAccount.tenant_id == tenant_id)
        .all()
    )

    net_income = Decimal("0")
    entries_created = 0

    # Close income accounts to income summary.
    for a in accounts:
        if a.type != "income":
            continue
        balance = _coa_balance(db, a.id, start, end)
        if balance == 0:
            continue
        # Income has credit balance. To zero it, debit income, credit summary.
        db.add(
            models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=end,
                description=f"Close {a.name} for {year}",
                debit_coa_account_id=a.id,
                credit_coa_account_id=income_summary.id,
                amount=balance,
                memo=f"Year-end close {year}",
                entry_type="adjusting",
            )
        )
        entries_created += 1
        net_income += balance

    # Close expense accounts to income summary.
    for a in accounts:
        if a.type != "expense":
            continue
        balance = _coa_balance(db, a.id, start, end)
        if balance == 0:
            continue
        # Expense has debit balance. To zero it, credit expense, debit summary.
        db.add(
            models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=end,
                description=f"Close {a.name} for {year}",
                debit_coa_account_id=income_summary.id,
                credit_coa_account_id=a.id,
                amount=-balance,
                memo=f"Year-end close {year}",
                entry_type="adjusting",
            )
        )
        entries_created += 1
        net_income += balance

    # Move net income/loss from income summary to retained earnings.
    summary_balance = net_income

    if summary_balance != 0:
        if summary_balance > 0:
            # Net profit: debit summary, credit retained earnings.
            debit_acct = income_summary
            credit_acct = retained_earnings
        else:
            # Net loss: debit retained earnings, credit summary.
            debit_acct = retained_earnings
            credit_acct = income_summary
        db.add(
            models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=end,
                description=f"Close Income Summary to Retained Earnings for {year}",
                debit_coa_account_id=debit_acct.id,
                credit_coa_account_id=credit_acct.id,
                amount=abs(summary_balance),
                memo=f"Year-end close {year}",
                entry_type="adjusting",
            )
        )
        entries_created += 1

    # Mark all periods in the year as closed.
    periods = (
        db.query(models.Period)
        .filter(
            models.Period.tenant_id == tenant_id,
            models.Period.start_date >= start,
            models.Period.end_date <= end,
        )
        .all()
    )
    closed_periods = 0
    for p in periods:
        if not p.is_closed:
            p.is_closed = True
            p.closed_at = datetime.now(timezone.utc)
            closed_periods += 1

    db.commit()

    return {
        "year": year,
        "entries_created": entries_created,
        "closed_periods": closed_periods,
        "net_income": float(summary_balance),
    }
