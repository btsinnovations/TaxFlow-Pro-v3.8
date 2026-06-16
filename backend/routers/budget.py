"""
Budget router: CRUD for budgets with entries, plus budget-vs-actual reporting.
"""
import os
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/budgets", tags=["budget"])


class BudgetWithEntriesResponse(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    name: str
    period_start: str
    period_end: str
    total_budget: float
    is_active: bool
    created_at: datetime
    entries: List[schemas.BudgetEntry]

    class Config:
        from_attributes = True


class BudgetVsActualEntry(BaseModel):
    category: str
    budgeted: float
    actual: float
    variance: float
    variance_pct: Optional[float] = None


class BudgetVsActualResponse(BaseModel):
    budget_id: int
    client_id: int
    period_start: str
    period_end: str
    entries: List[BudgetVsActualEntry]
    total_budgeted: float
    total_actual: float
    total_variance: float


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.Budget)
def create_budget(
    data: schemas.BudgetCreate,
    client_id: int = Query(..., description="Client ID (tenant)"),
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

    total = sum(e.amount for e in data.entries) if data.entries else 0.0

    budget = models.Budget(
        tenant_id=client_id,
        user_id=current_user.id,
        name=data.name,
        period_start=data.period_start,
        period_end=data.period_end,
        total_budget=total,
        is_active=data.is_active,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)

    for entry_data in data.entries:
        entry = models.BudgetEntry(
            budget_id=budget.id,
            tenant_id=client_id,
            category=entry_data.category,
            amount=entry_data.amount,
        )
        db.add(entry)

    db.commit()
    db.refresh(budget)

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="budget_create",
        entity_type="budget",
        entity_id=budget.id,
        details=f"Created budget '{data.name}' with {len(data.entries)} entries",
    )
    db.add(audit)
    db.commit()

    return budget


@router.get("", response_model=List[schemas.Budget])
def list_budgets(
    client_id: int = Query(..., description="Client ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(models.Budget).filter(models.Budget.tenant_id == client_id)
    if year is not None:
        year_str = str(year)
        query = query.filter(
            and_(
                models.Budget.period_start.like(f"{year_str}%"),
            )
        )
    budgets = query.order_by(models.Budget.created_at.desc()).all()
    return budgets


@router.get("/{budget_id}", response_model=BudgetWithEntriesResponse)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budget = (
        db.query(models.Budget)
        .filter(models.Budget.id == budget_id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return BudgetWithEntriesResponse(
        id=budget.id,
        tenant_id=budget.tenant_id,
        user_id=budget.user_id,
        name=budget.name,
        period_start=budget.period_start,
        period_end=budget.period_end,
        total_budget=float(budget.total_budget) if budget.total_budget else 0.0,
        is_active=budget.is_active,
        created_at=budget.created_at,
        entries=[
            schemas.BudgetEntry(
                id=e.id,
                budget_id=e.budget_id,
                tenant_id=e.tenant_id,
                category=e.category,
                amount=float(e.amount) if e.amount else 0.0,
                created_at=e.created_at,
            )
            for e in budget.entries
        ],
    )


@router.put("/{budget_id}", response_model=BudgetWithEntriesResponse)
def update_budget(
    budget_id: int,
    data: schemas.BudgetCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budget = (
        db.query(models.Budget)
        .filter(models.Budget.id == budget_id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    budget.name = data.name
    budget.period_start = data.period_start
    budget.period_end = data.period_end
    budget.is_active = data.is_active

    # Replace entries
    db.query(models.BudgetEntry).filter(
        models.BudgetEntry.budget_id == budget_id
    ).delete(synchronize_session=False)

    total = 0.0
    for entry_data in data.entries:
        entry = models.BudgetEntry(
            budget_id=budget_id,
            tenant_id=budget.tenant_id,
            category=entry_data.category,
            amount=entry_data.amount,
        )
        db.add(entry)
        total += entry_data.amount

    budget.total_budget = total
    db.commit()
    db.refresh(budget)

    audit = models.AuditEntry(
        tenant_id=budget.tenant_id,
        user_id=current_user.id,
        action="budget_update",
        entity_type="budget",
        entity_id=budget_id,
        details=f"Updated budget '{data.name}'",
    )
    db.add(audit)
    db.commit()

    return BudgetWithEntriesResponse(
        id=budget.id,
        tenant_id=budget.tenant_id,
        user_id=budget.user_id,
        name=budget.name,
        period_start=budget.period_start,
        period_end=budget.period_end,
        total_budget=float(budget.total_budget) if budget.total_budget else 0.0,
        is_active=budget.is_active,
        created_at=budget.created_at,
        entries=[
            schemas.BudgetEntry(
                id=e.id,
                budget_id=e.budget_id,
                tenant_id=e.tenant_id,
                category=e.category,
                amount=float(e.amount) if e.amount else 0.0,
                created_at=e.created_at,
            )
            for e in budget.entries
        ],
    )


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budget = (
        db.query(models.Budget)
        .filter(models.Budget.id == budget_id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(budget)
    db.commit()
    return None


@router.get("/{budget_id}/vs-actual", response_model=BudgetVsActualResponse)
def budget_vs_actual(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    budget = (
        db.query(models.Budget)
        .filter(models.Budget.id == budget_id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    if budget.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get actual transactions in the budget period
    actuals = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.client_id == budget.tenant_id,
            models.Transaction.date >= budget.period_start,
            models.Transaction.date <= budget.period_end,
            models.Transaction.archived == False,
        )
        .all()
    )

    # Sum actuals by category
    actual_by_cat = {}
    for tx in actuals:
        cat = (tx.category or "uncategorized").lower()
        amt = float(tx.amount) if tx.amount else 0.0
        if tx.tx_type == "debit":
            actual_by_cat[cat] = actual_by_cat.get(cat, 0.0) + amt

    # Build comparison
    entries = []
    total_budgeted = 0.0
    total_actual = 0.0

    # Use all budget categories plus any actual-only categories
    all_cats = set()
    budget_cats = {}
    for e in budget.entries:
        cat = e.category.lower()
        all_cats.add(cat)
        budget_cats[cat] = float(e.amount) if e.amount else 0.0

    for cat in actual_by_cat:
        all_cats.add(cat)

    for cat in sorted(all_cats):
        budgeted = budget_cats.get(cat, 0.0)
        actual = actual_by_cat.get(cat, 0.0)
        variance = budgeted - actual
        variance_pct = None
        if budgeted != 0:
            variance_pct = round((variance / budgeted) * 100, 2)

        entries.append(
            BudgetVsActualEntry(
                category=cat,
                budgeted=round(budgeted, 2),
                actual=round(actual, 2),
                variance=round(variance, 2),
                variance_pct=variance_pct,
            )
        )
        total_budgeted += budgeted
        total_actual += actual

    return BudgetVsActualResponse(
        budget_id=budget_id,
        client_id=budget.tenant_id,
        period_start=budget.period_start,
        period_end=budget.period_end,
        entries=entries,
        total_budgeted=round(total_budgeted, 2),
        total_actual=round(total_actual, 2),
        total_variance=round(total_budgeted - total_actual, 2),
    )
