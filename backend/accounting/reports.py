"""Financial reports domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


def profit_and_loss(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Return a simple P&L by GL account type for the date range."""
    txns = db.query(models.Transaction).join(models.Statement).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == user_id,
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
    ).all()
    income = Decimal("0")
    expenses = Decimal("0")
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        if t.tx_type and t.tx_type.lower() in ("credit", "deposit", "income"):
            income += amt
        else:
            expenses += amt
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "income": float(income),
        "expenses": float(expenses),
        "net": float(income - expenses),
    }


def trial_balance(
    db: Session,
    tenant_id: int,
    user_id: int,
    as_of: date,
) -> list[dict]:
    """Return trial balance by GL account."""
    accounts = db.query(models.GLAccount).filter(
        models.GLAccount.tenant_id == tenant_id,
        models.GLAccount.user_id == user_id,
    ).all()
    rows = []
    for acct in accounts:
        txns = db.query(models.Transaction).filter(
            models.Transaction.gl_account_id == acct.id,
            models.Transaction.date <= as_of,
        ).all()
        debit = Decimal("0")
        credit = Decimal("0")
        for t in txns:
            amt = Decimal(str(t.amount or 0))
            if t.tx_type and t.tx_type.lower() in ("debit", "expense", "check"):
                debit += amt
            else:
                credit += amt
        rows.append({
            "account_id": acct.id,
            "code": acct.code,
            "name": acct.name,
            "debit": float(debit),
            "credit": float(credit),
        })
    return rows
