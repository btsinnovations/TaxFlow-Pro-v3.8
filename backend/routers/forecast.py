"""
Forecast router: generate monthly financial predictions.
- Uses RecurringTemplate to project future transactions
- Falls back to averaging last 6 months of actual transactions
"""
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/forecast", tags=["forecast"])


class ForecastMonthEntry(BaseModel):
    month: str
    year_month: str
    predicted_income: float
    predicted_expenses: float
    net: float


class ForecastResponse(BaseModel):
    client_id: int
    months_ahead: int
    methodology: str
    entries: List[ForecastMonthEntry]
    total_predicted_income: float
    total_predicted_expenses: float
    total_net: float


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _month_label(dt: datetime) -> str:
    return dt.strftime("%B %Y")


def _parse_date(date_str: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _avg_monthly_from_history(db: Session, client_id: int, months_back: int = 6) -> dict:
    """Average monthly income/expense from last N months of actual transactions."""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=months_back * 31)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.tenant_id == client_id,
            models.Transaction.date >= start_str,
            models.Transaction.date <= end_str,
            models.Transaction.archived == False,
        )
        .all()
    )

    monthly = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    for tx in txs:
        dt = _parse_date(tx.date)
        if not dt:
            continue
        mk = _month_key(dt)
        amt = float(tx.amount) if tx.amount else 0.0
        if tx.tx_type == "credit":
            monthly[mk]["income"] += amt
        else:
            monthly[mk]["expenses"] += amt

    if not monthly:
        return {"income": 0.0, "expenses": 0.0}

    avg_income = sum(m["income"] for m in monthly.values()) / len(monthly)
    avg_expenses = sum(m["expenses"] for m in monthly.values()) / len(monthly)
    return {"income": avg_income, "expenses": avg_expenses}


def _generate_from_templates(
    db: Session, client_id: int, months_ahead: int
) -> List[ForecastMonthEntry]:
    """Generate predictions from active RecurringTemplate entries."""
    templates = (
        db.query(models.RecurringTemplate)
        .filter(
            models.RecurringTemplate.tenant_id == client_id,
            models.RecurringTemplate.is_active == True,
        )
        .all()
    )

    now = datetime.utcnow()
    entries = []

    for i in range(1, months_ahead + 1):
        proj_dt = now + timedelta(days=i * 30)
        ym = _month_key(proj_dt)
        label = _month_label(proj_dt)
        income = 0.0
        expenses = 0.0

        for tmpl in templates:
            if tmpl.start_date:
                tmpl_start = _parse_date(tmpl.start_date)
                if tmpl_start and proj_dt < tmpl_start:
                    continue
            if tmpl.end_date:
                tmpl_end = _parse_date(tmpl.end_date)
                if tmpl_end and proj_dt > tmpl_end:
                    continue

            # Check frequency applicability
            include = False
            freq = (tmpl.frequency or "").lower()
            if freq == "monthly":
                include = True
            elif freq == "weekly":
                include = True  # Weekly items apply every month
            elif freq == "bi-weekly":
                include = True
            elif freq == "quarterly":
                include = (i % 3) == 1
            elif freq == "annually":
                include = i == 1
            elif freq == "yearly":
                include = i == 1
            else:
                include = True

            if not include:
                continue

            amt = float(tmpl.amount) if tmpl.amount else 0.0
            if tmpl.tx_type == "credit":
                income += amt
            else:
                expenses += amt

        net = income - expenses
        entries.append(
            ForecastMonthEntry(
                month=label,
                year_month=ym,
                predicted_income=round(income, 2),
                predicted_expenses=round(expenses, 2),
                net=round(net, 2),
            )
        )

    return entries


def _generate_from_history(
    db: Session, client_id: int, months_ahead: int
) -> List[ForecastMonthEntry]:
    """Generate predictions by averaging last 6 months of actuals."""
    avg = _avg_monthly_from_history(db, client_id, months_back=6)
    now = datetime.utcnow()
    entries = []

    for i in range(1, months_ahead + 1):
        proj_dt = now + timedelta(days=i * 30)
        ym = _month_key(proj_dt)
        label = _month_label(proj_dt)
        income = avg["income"]
        expenses = avg["expenses"]
        net = income - expenses
        entries.append(
            ForecastMonthEntry(
                month=label,
                year_month=ym,
                predicted_income=round(income, 2),
                predicted_expenses=round(expenses, 2),
                net=round(net, 2),
            )
        )

    return entries


@router.get("", response_model=ForecastResponse)
def get_forecast(
    client_id: int = Query(..., description="Client ID"),
    months_ahead: int = Query(12, ge=1, le=60, description="Number of months to project"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    templates = (
        db.query(models.RecurringTemplate)
        .filter(
            models.RecurringTemplate.tenant_id == client_id,
            models.RecurringTemplate.is_active == True,
        )
        .all()
    )

    if templates:
        entries = _generate_from_templates(db, client_id, months_ahead)
        methodology = "recurring_templates"
    else:
        entries = _generate_from_history(db, client_id, months_ahead)
        methodology = "historical_average_6m"

    total_income = sum(e.predicted_income for e in entries)
    total_expenses = sum(e.predicted_expenses for e in entries)
    total_net = sum(e.net for e in entries)

    return ForecastResponse(
        client_id=client_id,
        months_ahead=months_ahead,
        methodology=methodology,
        entries=entries,
        total_predicted_income=round(total_income, 2),
        total_predicted_expenses=round(total_expenses, 2),
        total_net=round(total_net, 2),
    )
