"""Loans / credit lines API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.liabilities import (
    LiabilityError,
    compute_amortization_schedule,
    create_loan_schedule,
    credit_line_available,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/liabilities", tags=["liabilities"])


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


class LoanScheduleRequest(BaseModel):
    account_id: int
    original_principal: float
    annual_rate: float
    term_months: int
    start_date: date


class AmortizationRequest(BaseModel):
    principal: float
    annual_rate: float
    term_months: int
    start_date: date


@router.post("/loan-schedule", response_model=dict)
def create_loan(
    request: Request,
    payload: LoanScheduleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        ls = create_loan_schedule(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            account_id=payload.account_id,
            original_principal=Decimal(str(payload.original_principal)),
            annual_rate=Decimal(str(payload.annual_rate)),
            term_months=payload.term_months,
            start_date=payload.start_date,
        )
    except LiabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": ls.id,
        "account_id": ls.account_id,
        "payment_amount": float(ls.payment_amount),
        "schedule": __import__("json").loads(ls.schedule_json or "[]"),
    }


@router.post("/amortization", response_model=list[dict])
def amortization(
    request: Request,
    payload: AmortizationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    return compute_amortization_schedule(
        Decimal(str(payload.principal)),
        Decimal(str(payload.annual_rate)),
        payload.term_months,
        payload.start_date,
    )


@router.get("/{account_id}/available-credit")
def available_credit(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    try:
        available = credit_line_available(db, account_id=account_id, user_id=current_user.id)
    except LiabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"account_id": account_id, "available_credit": float(available)}
