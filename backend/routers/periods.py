"""Periods router — close/reopen/status endpoints for TaxFlow Pro v3.11.6 R2."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.period_close import (
    PeriodCloseError,
    close_period,
    reopen_period,
    get_period_status,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role

router = APIRouter(prefix="/periods", tags=["periods"])


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


@router.post("/{period_id}/close")
def close_period_endpoint(
    request: Request,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    try:
        period = close_period(db, tenant_id=tenant_id, user_id=current_user.id,
                              period_id=period_id, profile_id=tenant_id)
    except PeriodCloseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": period.id, "name": period.name, "is_closed": period.is_closed}


@router.post("/{period_id}/reopen")
def reopen_period_endpoint(
    request: Request,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.admin)
    try:
        period = reopen_period(db, tenant_id=tenant_id, user_id=current_user.id, period_id=period_id)
    except PeriodCloseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": period.id, "name": period.name, "is_closed": period.is_closed}


@router.get("/{period_id}/status")
def period_status_endpoint(
    request: Request,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    try:
        return get_period_status(db, tenant_id=tenant_id, period_id=period_id)
    except PeriodCloseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc