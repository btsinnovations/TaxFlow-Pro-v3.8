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
    manual_match,
    unmatch,
    list_unmatched,
    get_matches,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

from backend.local.roles import Role, has_role
from backend.accounting.reconciliation_lock import (
    ReconciliationLockError,
    complete_reconciliation,
    reopen_reconciliation,
)

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


def _require_role(db: Session, current_user: models.User, tenant_id: int, min_role: Role):
    if not has_role(db, current_user.id, tenant_id, min_role):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient profile role ({min_role.name} required)",
        )


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
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
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
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
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


class ManualMatchRequest(BaseModel):
    ledger_tx_id: int
    statement_tx_id: str


@router.post("/{import_id}/manual-match", response_model=dict)
def manual_match_route(
    request: Request,
    import_id: int,
    payload: ManualMatchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    try:
        m = manual_match(
            db,
            import_id=import_id,
            user_id=current_user.id,
            ledger_tx_id=payload.ledger_tx_id,
            statement_tx_id=payload.statement_tx_id,
        )
    except ReconciliationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": m.id,
        "ledger_tx_id": m.ledger_tx_id,
        "statement_tx_id": m.statement_tx_id,
        "match_type": m.match_type,
        "status": m.status,
    }


@router.post("/{import_id}/unmatch", response_model=dict)
def unmatch_route(
    request: Request,
    import_id: int,
    payload: ManualMatchRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    try:
        ok = unmatch(
            db,
            import_id=import_id,
            user_id=current_user.id,
            statement_tx_id=payload.statement_tx_id,
        )
    except ReconciliationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": ok}


@router.get("/{import_id}/unmatched")
def unmatched_route(
    request: Request,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    try:
        return list_unmatched(db, import_id=import_id, user_id=current_user.id)
    except ReconciliationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{import_id}/matches")
def matches_route(
    request: Request,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    try:
        rows = get_matches(db, import_id=import_id, user_id=current_user.id)
    except ReconciliationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        {
            "id": m.id,
            "ledger_tx_id": m.ledger_tx_id,
            "statement_tx_id": m.statement_tx_id,
            "match_type": m.match_type,
            "status": m.status,
        }
        for m in rows
    ]


@router.get("/{import_id}/status")
def status_route(
    request: Request,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    try:
        return reconciliation_status(db, import_id=import_id, user_id=current_user.id)
    except ReconciliationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{import_id}/complete")
def complete_reconciliation_endpoint(
    request: Request,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Complete (lock) a reconciliation."""
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    try:
        imp = complete_reconciliation(
            db, import_id=import_id, user_id=current_user.id,
            tenant_id=tenant_id, profile_id=tenant_id,
        )
    except ReconciliationLockError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": imp.id, "is_completed": imp.is_completed}


@router.post("/{import_id}/reopen")
def reopen_reconciliation_endpoint(
    request: Request,
    import_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Reopen a completed reconciliation."""
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.admin)
    try:
        imp = reopen_reconciliation(
            db, import_id=import_id, user_id=current_user.id,
            tenant_id=tenant_id,
        )
    except ReconciliationLockError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": imp.id, "is_completed": imp.is_completed}
