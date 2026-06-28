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


def cash_flow_forecast_13_week(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
) -> list[dict]:
    """Project weekly cash balance for the next 13 weeks.

    Combines:
      - opening cash from bank account statement closing balances
      - recurring rules scheduled within the window
      - open invoices (receivables) and bills (payables)
    """
    from datetime import timedelta

    accounts = db.query(models.Account).filter(
        models.Account.tenant_id == tenant_id,
        models.Account.user_id == user_id,
    ).all()
    opening = Decimal("0")
    for account in accounts:
        for stmt in account.statements:
            if stmt.closing_balance is not None:
                opening += Decimal(str(stmt.closing_balance))

    rules = db.query(models.RecurringRule).filter(
        models.RecurringRule.tenant_id == tenant_id,
        models.RecurringRule.user_id == user_id,
        models.RecurringRule.is_active == True,
        models.RecurringRule.next_date >= start_date,
    ).all()

    invoices = db.query(models.Invoice).filter(
        models.Invoice.tenant_id == tenant_id,
        models.Invoice.user_id == user_id,
        models.Invoice.status != "paid",
    ).all()

    weeks = []
    balance = opening
    for i in range(13):
        week_start = start_date + timedelta(days=7 * i)
        week_end = week_start + timedelta(days=6)
        delta = Decimal("0")

        for rule in rules:
            nd = rule.next_date
            if nd is None:
                continue
            if week_start <= nd <= week_end:
                amt = Decimal(str(rule.amount or 0))
                # Naive classification: if description contains 'bill'/'expense', treat as outflow.
                is_outflow = any(kw in (rule.description or "").lower() for kw in ("bill", "expense", "payment"))
                delta += -amt if is_outflow else amt

        for inv in invoices:
            remaining = Decimal(str(inv.total or 0)) - Decimal(str(inv.amount_paid or 0))
            if inv.due_date is not None and week_start <= inv.due_date <= week_end:
                if inv.is_bill:
                    delta -= remaining
                else:
                    delta += remaining

        balance += delta
        weeks.append({
            "week": i + 1,
            "start_date": week_start.isoformat(),
            "end_date": week_end.isoformat(),
            "opening_cash": float(opening.quantize(Decimal("0.01"))),
            "projected_change": float(delta.quantize(Decimal("0.01"))),
            "projected_cash": float(balance.quantize(Decimal("0.01"))),
        })
        opening = balance
    return weeks


def variance_alerts(
    db: Session,
    tenant_id: int,
    user_id: int,
    period: str,
    threshold: float = 0.1,
) -> list[dict]:
    """Return budget lines where actual exceeds budget by the given threshold."""
    rows = budget_vs_actual(db, tenant_id, user_id, period)
    alerts = []
    for r in rows:
        budget = Decimal(str(r["budget"]))
        actual = Decimal(str(r["actual"]))
        if budget > 0 and actual > budget * (Decimal("1") + Decimal(str(threshold))):
            alerts.append({
                "account_id": r["account_id"],
                "period": r["period"],
                "budget": r["budget"],
                "actual": r["actual"],
                "variance": r["variance"],
                "over_budget_pct": float(((actual - budget) / budget).quantize(Decimal("0.0001"))),
            })
    return alerts
