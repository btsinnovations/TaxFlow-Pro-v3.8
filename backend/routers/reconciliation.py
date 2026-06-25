"""Bank reconciliation API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.reconciliation import (
    ReconciliationError,
    import_statement as import_reconciliation,
    auto_match,
    reconciliation_status,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


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


class ImportRequest(BaseModel):
    account_id: int
    statement_balance: float
    statement_date: date
    filename: str | None = None


@router.post("/import", response_model=dict)
def import_statement(
    request: Request,
    payload: ImportRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        ri = import_reconciliation(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            account_id=payload.account_id,
            statement_balance=Decimal(str(payload.statement_balance)),
            statement_date=payload.statement_date,
            filename=payload.filename,
        )
    except ReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": ri.id,
        "account_id": ri.account_id,
        "statement_balance": float(ri.statement_balance),
        "statement_date": ri.statement_date.isoformat(),
    }


class AutoMatchRequest(BaseModel):
    statement_rows: list[dict] | None = None


@router.post("/{import_id}/auto-match", response_model=list[dict])
def auto_match_route(
    request: Request,
    import_id: int,
    payload: AutoMatchRequest | None = None,
    window_days: int = 3,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    try:
        return auto_match(
            db,
            import_id=import_id,
            user_id=current_user.id,
            date_window_days=window_days,
            statement_rows=(payload.statement_rows if payload else None),
        )
    except ReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{import_id}/status")
def status_route(
    request: Request,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    try:
        return reconciliation_status(db, import_id=import_id, user_id=current_user.id)
    except ReconciliationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
