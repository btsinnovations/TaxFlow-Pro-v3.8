"""Budget & cash-flow forecast API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.budget import (
    set_budget_line,
    budget_vs_actual,
    cash_flow_forecast,
    cash_flow_forecast_13_week,
    variance_alerts,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role

router = APIRouter(prefix="/budget", tags=["budget"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User) -> int:
    if not is_postgres():
        return resolve_user_tenant_id(current_user)
    if local_settings.is_single_user():
        tenant_id = resolve_user_tenant_id(current_user)
        set_tenant_id(db, tenant_id)
        return tenant_id
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    try:
        return int(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header")


def _require_role(db: Session, current_user: models.User, tenant_id: int, min_role: Role):
    if not has_role(db, current_user.id, tenant_id, min_role):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient profile role ({min_role.name} required)",
        )


class BudgetLineRequest(BaseModel):
    account_id: int
    period: str  # YYYY-MM
    amount: float


@router.post("/lines", response_model=dict)
def set_line(
    request: Request,
    payload: BudgetLineRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    line = set_budget_line(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        account_id=payload.account_id,
        period=payload.period,
        amount=Decimal(str(payload.amount)),
    )
    return {
        "id": line.id,
        "account_id": line.account_id,
        "period": line.period,
        "budget_amount": float(line.budget_amount),
    }


@router.get("/{period}/vs-actual")
def vs_actual(
    request: Request,
    period: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return budget_vs_actual(db, tenant_id=tenant_id, user_id=current_user.id, period=period)


@router.get("/cash-flow")
def cash_flow(
    request: Request,
    start: date,
    months: int = 6,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return cash_flow_forecast(db, tenant_id=tenant_id, user_id=current_user.id,
                              start_date=start, months=months)


@router.get("/cash-flow-13-week")
def cash_flow_13_week(
    request: Request,
    start: date,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return cash_flow_forecast_13_week(db, tenant_id=tenant_id, user_id=current_user.id,
                                      start_date=start)


@router.get("/{period}/variance-alerts")
def variance_alert_list(
    request: Request,
    period: str,
    threshold: float = 0.1,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return variance_alerts(db, tenant_id=tenant_id, user_id=current_user.id,
                           period=period, threshold=threshold)
