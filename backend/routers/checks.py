"""Check register API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.checks import CheckError, issue_check, list_checks, void_check
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

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


class IssueCheckRequest(BaseModel):
    account_id: int
    payee: str
    amount: float
    date: date
    memo: str | None = None


class VoidCheckRequest(BaseModel):
    reason: str | None = None


@router.get("/{account_id}", response_model=list[dict])
def get_checks(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    rows = list_checks(db, account_id=account_id, user_id=current_user.id)
    return [
        {
            "id": t.id,
            "date": t.date.isoformat() if t.date else None,
            "description": t.description,
            "amount": float(t.amount) if t.amount is not None else None,
            "tx_type": t.tx_type,
            "workpaper_ref": t.workpaper_ref,
        }
        for t in rows
    ]


@router.post("/", response_model=dict, status_code=201)
def issue_check_route(
    request: Request,
    payload: IssueCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
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
        )
    except CheckError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "date": txn.date.isoformat() if txn.date else None,
        "description": txn.description,
        "amount": float(txn.amount) if txn.amount is not None else None,
        "workpaper_ref": txn.workpaper_ref,
    }


@router.patch("/{transaction_id}/void", response_model=dict)
def void_check_route(
    request: Request,
    transaction_id: int,
    payload: VoidCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    try:
        txn = void_check(db, transaction_id=transaction_id, user_id=current_user.id, reason=payload.reason)
    except CheckError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "description": txn.description,
        "tx_type": txn.tx_type,
    }
