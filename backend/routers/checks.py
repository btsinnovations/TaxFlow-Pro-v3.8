"""Check register API endpoints for TaxFlow Pro v3.11.6 B2.

Enhanced with:
- Proper Check model (check_number, payee, amount, date, account, memo).
- Duplicate check number prevention per account.
- Search by check number range.
- Mark cleared/reconciled.
- Optional link to transaction.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.checks import (
    CheckError,
    record_check,
    list_checks,
    get_check,
    update_check,
    mark_cleared,
    mark_reconciled,
    void_check,
    delete_check,
    search_by_number_range,
    issue_check,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.audit import record, AuditAction, AuditResource

router = APIRouter(prefix="/checks", tags=["checks"])


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


def _check_to_dict(check: models.Check) -> dict:
    return {
        "id": check.id,
        "account_id": check.account_id,
        "tenant_id": check.tenant_id,
        "check_number": check.check_number,
        "payee": check.payee,
        "amount": float(check.amount) if check.amount is not None else None,
        "date": check.date.isoformat() if check.date else None,
        "memo": check.memo,
        "status": check.status,
        "transaction_id": check.transaction_id,
        "created_at": check.created_at.isoformat() if check.created_at else None,
    }


class RecordCheckRequest(BaseModel):
    account_id: int
    check_number: str
    payee: str
    amount: float
    date: date
    memo: Optional[str] = None
    transaction_id: Optional[int] = None


class UpdateCheckRequest(BaseModel):
    payee: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[date] = None
    memo: Optional[str] = None
    status: Optional[str] = None
    transaction_id: Optional[int] = None


class VoidCheckRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/", response_model=list[dict])
def list_checks_route(
    request: Request,
    account_id: Optional[int] = None,
    start_number: Optional[str] = None,
    end_number: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List checks for the current tenant with optional filters."""
    tenant_id = _wrap_tenant(request, db, current_user)
    checks = list_checks(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        account_id=account_id,
        start_number=start_number,
        end_number=end_number,
        status=status,
    )
    return [_check_to_dict(c) for c in checks]


@router.post("/", response_model=dict, status_code=201)
def record_check_route(
    request: Request,
    payload: RecordCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Record a new check in the register."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        check = record_check(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            account_id=payload.account_id,
            check_number=payload.check_number,
            payee=payload.payee,
            amount=Decimal(str(payload.amount)),
            date_value=payload.date,
            memo=payload.memo,
            transaction_id=payload.transaction_id,
        )
    except CheckError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record(
        db,
        current_user,
        AuditAction.CREATE,
        AuditResource.TRANSACTION,
        check.id,
        {"check_number": check.check_number, "payee": check.payee},
    )
    return _check_to_dict(check)


@router.get("/{check_id}", response_model=dict)
def get_check_route(
    request: Request,
    check_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get a single check by ID."""
    tenant_id = _wrap_tenant(request, db, current_user)
    check = get_check(db, check_id=check_id, tenant_id=tenant_id)
    if check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    return _check_to_dict(check)


@router.put("/{check_id}", response_model=dict)
def update_check_route(
    request: Request,
    check_id: int,
    payload: UpdateCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update a check entry."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        check = update_check(
            db,
            check_id=check_id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            payee=payload.payee,
            amount=Decimal(str(payload.amount)) if payload.amount is not None else None,
            date_value=payload.date,
            memo=payload.memo,
            status=payload.status,
            transaction_id=payload.transaction_id,
        )
    except CheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record(
        db,
        current_user,
        AuditAction.UPDATE,
        AuditResource.TRANSACTION,
        check.id,
        {"updated_fields": [k for k, v in payload.model_dump(exclude_unset=True).items() if v is not None]},
    )
    return _check_to_dict(check)


@router.delete("/{check_id}")
def delete_check_route(
    request: Request,
    check_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a check entry."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        delete_check(db, check_id=check_id, tenant_id=tenant_id, user_id=current_user.id)
    except CheckError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record(
        db,
        current_user,
        AuditAction.DELETE,
        AuditResource.TRANSACTION,
        check_id,
        {},
    )
    return {"ok": True}


@router.patch("/{check_id}/clear", response_model=dict)
def clear_check_route(
    request: Request,
    check_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark a check as cleared."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        check = mark_cleared(db, check_id=check_id, tenant_id=tenant_id, user_id=current_user.id)
    except CheckError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _check_to_dict(check)


@router.patch("/{check_id}/reconcile", response_model=dict)
def reconcile_check_route(
    request: Request,
    check_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Mark a check as reconciled."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        check = mark_reconciled(db, check_id=check_id, tenant_id=tenant_id, user_id=current_user.id)
    except CheckError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _check_to_dict(check)


@router.patch("/{check_id}/void", response_model=dict)
def void_check_route(
    request: Request,
    check_id: int,
    payload: VoidCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Void a check."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        check = void_check(db, check_id=check_id, tenant_id=tenant_id, user_id=current_user.id, reason=payload.reason)
    except CheckError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _check_to_dict(check)


@router.get("/search/range", response_model=list[dict])
def search_by_range_route(
    request: Request,
    account_id: int,
    start: str,
    end: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Search checks by check number range (inclusive)."""
    tenant_id = _wrap_tenant(request, db, current_user)
    checks = search_by_number_range(
        db,
        tenant_id=tenant_id,
        account_id=account_id,
        start=start,
        end=end,
    )
    return [_check_to_dict(c) for c in checks]


# ---------------------------------------------------------------------------
# Legacy compatibility: issue_check creates a Transaction with tx_type="check"
# plus a Check record. Existing tests use this endpoint.
# ---------------------------------------------------------------------------

class IssueCheckRequest(BaseModel):
    account_id: int
    payee: str
    amount: float
    date: date
    memo: Optional[str] = None
    check_number: Optional[str] = None


@router.post("/issue", response_model=dict, status_code=201)
def issue_check_route(
    request: Request,
    payload: IssueCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Issue a check (creates both a Check record and a Transaction)."""
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        txn = issue_check(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            account_id=payload.account_id,
            payee=payload.payee,
            amount=Decimal(str(payload.amount)),
            date_value=payload.date,
            memo=payload.memo,
            check_number=payload.check_number,
        )
    except CheckError as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "date": txn.date.isoformat() if txn.date else None,
        "description": txn.description,
        "amount": float(txn.amount) if txn.amount is not None else None,
        "workpaper_ref": txn.workpaper_ref,
    }