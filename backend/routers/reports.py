"""Financial reports API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.reports import (
    profit_and_loss,
    trial_balance,
    balance_sheet,
    cash_flow_statement,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role

router = APIRouter(prefix="/reports", tags=["reports"])


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


class DateRange(BaseModel):
    start_date: date
    end_date: date


@router.post("/profit-and-loss")
def pnl_route(
    request: Request,
    payload: DateRange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Insufficient profile role (viewer required)")
    return profit_and_loss(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )


@router.post("/trial-balance")
def trial_balance_route(
    request: Request,
    as_of: date,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Insufficient profile role (viewer required)")
    return {"as_of": as_of.isoformat(), "rows": trial_balance(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        as_of=as_of,
    )}


@router.post("/balance-sheet")
def balance_sheet_route(
    request: Request,
    as_of: date,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Insufficient profile role (viewer required)")
    return balance_sheet(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        as_of=as_of,
    )


@router.post("/cash-flow")
def cash_flow_route(
    request: Request,
    payload: DateRange,
    basis: str = "accrual",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Insufficient profile role (viewer required)")
    if basis not in ("accrual", "cash"):
        raise HTTPException(status_code=400, detail="basis must be 'accrual' or 'cash'")
    return cash_flow_statement(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        basis=basis,
    )
