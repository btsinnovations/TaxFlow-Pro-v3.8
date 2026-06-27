"""Budget & cash-flow forecast domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


def set_budget_line(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    period: str,  # YYYY-MM
    amount: Decimal,
) -> models.BudgetLine:
    """Set or update a budget line for a GL account and period."""
    line = db.query(models.BudgetLine).filter(
        models.BudgetLine.tenant_id == tenant_id,
        models.BudgetLine.user_id == user_id,
        models.BudgetLine.account_id == account_id,
        models.BudgetLine.period == period,
    ).first()
    if line is None:
        line = models.BudgetLine(
            tenant_id=tenant_id,
            user_id=user_id,
            account_id=account_id,
            period=period,
            budget_amount=amount,
        )
        db.add(line)
    else:
        line.budget_amount = amount
    db.commit()
    db.refresh(line)
    return line


def budget_vs_actual(
    db: Session,
    tenant_id: int,
    user_id: int,
    period: str,
) -> list[dict]:
    """Return budget vs actual for a given period."""
    lines = db.query(models.BudgetLine).filter(
        models.BudgetLine.tenant_id == tenant_id,
        models.BudgetLine.user_id == user_id,
        models.BudgetLine.period == period,
    ).all()
    year, month = map(int, period.split("-"))
    start = date(year, month, 1)
    end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
    result = []
    for line in lines:
        actual = Decimal("0")
        txns = db.query(models.Transaction).filter(
            models.Transaction.coa_account_id == line.account_id,
            models.Transaction.date >= start,
            models.Transaction.date < end,
        ).all()
        for t in txns:
            actual += Decimal(str(t.amount or 0))
        result.append({
            "account_id": line.account_id,
            "period": line.period,
            "budget": float(line.budget_amount),
            "actual": float(actual),
            "variance": float(line.budget_amount - actual),
        })
    return result


def cash_flow_forecast(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    months: int = 6,
) -> list[dict]:
    """Project cash balance forward using recurring inflows/outflows."""
    # Stub: use historical net from last 3 months as monthly delta.
    end = start_date
    start = date(start_date.year - 1 if start_date.month <= 3 else start_date.year,
                 start_date.month - 3 if start_date.month > 3 else start_date.month + 9,
                 1)
    txns = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == user_id,
        models.Transaction.date >= start,
        models.Transaction.date < end,
    ).all()
    net = Decimal("0")
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        if t.tx_type and t.tx_type.lower() in ("credit", "deposit", "income"):
            net += amt
        else:
            net -= amt
    monthly_delta = net / Decimal("3")
    balance = Decimal("0")
    projection = []
    for i in range(months):
        balance += monthly_delta
        projection.append({
            "month": i + 1,
            "date": date(start_date.year + (start_date.month + i - 1) // 12,
                         ((start_date.month + i - 1) % 12) + 1, 1).isoformat(),
            "projected_cash": float(balance.quantize(Decimal("0.01"))),
        })
    return projection
