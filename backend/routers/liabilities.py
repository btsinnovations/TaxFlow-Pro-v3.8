from __future__ import annotations

from typing import Optional
"""Loans / credit lines API endpoints for TaxFlow Pro v3.11.

B3.01 — Full endpoints:
- POST /liabilities/loan-schedule — create loan with amortization
- GET  /liabilities/loan-schedule/{id} — get schedule with amortization table
- GET  /liabilities/loan-schedule — list all schedules
- POST /liabilities/loan-schedule/{id}/payments — record a payment
- GET  /liabilities/loan-schedule/{id}/payments — list payments
- GET  /liabilities/loan-schedule/{id}/upcoming — upcoming payments
- POST /liabilities/credit-lines — create credit line
- GET  /liabilities/credit-lines — list credit lines
- GET  /liabilities/credit-lines/{id} — get credit line details
- POST /liabilities/credit-lines/{id}/draw — draw on credit line
- POST /liabilities/credit-lines/{id}/payment — pay down credit line
- GET  /liabilities/credit-lines/{id}/available — available credit
- POST /liabilities/amortization — compute amortization without saving
"""

import json
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.liabilities import (
    LiabilityError,
    compute_amortization_schedule,
    create_loan_schedule,
    get_loan_schedule,
    list_loan_schedules,
    record_loan_payment,
    list_loan_payments,
    generate_upcoming_payments,
    create_credit_line,
    get_credit_line,
    list_credit_lines,
    credit_line_draw,
    credit_line_payment,
    credit_line_available,
    list_credit_line_transactions,
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

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


class PaymentRequest(BaseModel):
    payment_date: date
    payment_amount: float


class CreditLineCreate(BaseModel):
    account_id: int
    credit_limit: float
    annual_rate: float = 0.0
    start_date: Optional[date] = None


class CreditLineDraw(BaseModel):
    amount: float
    draw_date: date


class CreditLinePayment(BaseModel):
    amount: float
    payment_date: date


# ---------------------------------------------------------------------------
# Loan schedule endpoints
# ---------------------------------------------------------------------------

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
        "schedule": json.loads(ls.schedule_json or "[]"),
    }


@router.get("/loan-schedule", response_model=list[dict])
def list_schedules(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    schedules = list_loan_schedules(db, tenant_id=tenant_id)
    return [
        {
            "id": ls.id,
            "account_id": ls.account_id,
            "original_principal": float(ls.original_principal),
            "rate": float(ls.rate),
            "term_months": ls.term_months,
            "start_date": ls.start_date.isoformat(),
            "payment_amount": float(ls.payment_amount),
        }
        for ls in schedules
    ]


@router.get("/loan-schedule/{schedule_id}", response_model=dict)
def get_schedule(
    request: Request,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        ls = get_loan_schedule(db, schedule_id=schedule_id, tenant_id=tenant_id)
    except LiabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": ls.id,
        "account_id": ls.account_id,
        "original_principal": float(ls.original_principal),
        "rate": float(ls.rate),
        "term_months": ls.term_months,
        "start_date": ls.start_date.isoformat(),
        "payment_amount": float(ls.payment_amount),
        "schedule": json.loads(ls.schedule_json or "[]"),
    }


@router.post("/loan-schedule/{schedule_id}/payments", response_model=dict)
def make_payment(
    request: Request,
    schedule_id: int,
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        payment = record_loan_payment(
            db,
            schedule_id=schedule_id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            payment_date=payload.payment_date,
            payment_amount=Decimal(str(payload.payment_amount)),
        )
    except LiabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": payment.id,
        "payment_date": payment.payment_date.isoformat(),
        "payment_amount": float(payment.payment_amount),
        "principal_paid": float(payment.principal_paid),
        "interest_paid": float(payment.interest_paid),
        "remaining_principal": float(payment.remaining_principal),
    }


@router.get("/loan-schedule/{schedule_id}/payments", response_model=list[dict])
def get_payments(
    request: Request,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        payments = list_loan_payments(db, schedule_id=schedule_id, tenant_id=tenant_id)
    except LiabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        {
            "id": p.id,
            "payment_date": p.payment_date.isoformat(),
            "payment_amount": float(p.payment_amount),
            "principal_paid": float(p.principal_paid),
            "interest_paid": float(p.interest_paid),
            "remaining_principal": float(p.remaining_principal),
        }
        for p in payments
    ]


@router.get("/loan-schedule/{schedule_id}/upcoming", response_model=list[dict])
def get_upcoming(
    request: Request,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    months: int = Query(3, ge=1, le=60),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        return generate_upcoming_payments(
            db, schedule_id=schedule_id, tenant_id=tenant_id, months_ahead=months,
        )
    except LiabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Credit line endpoints
# ---------------------------------------------------------------------------

@router.post("/credit-lines", response_model=dict, status_code=201)
def create_cl(
    request: Request,
    payload: CreditLineCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        cl = create_credit_line(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            account_id=payload.account_id,
            credit_limit=Decimal(str(payload.credit_limit)),
            annual_rate=Decimal(str(payload.annual_rate)),
            start_date=payload.start_date,
        )
    except LiabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": cl.id,
        "account_id": cl.account_id,
        "credit_limit": float(cl.credit_limit),
        "current_balance": float(cl.current_balance),
        "annual_rate": float(cl.annual_rate),
    }


@router.get("/credit-lines", response_model=list[dict])
def list_cls(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    cls = list_credit_lines(db, tenant_id=tenant_id)
    return [
        {
            "id": cl.id,
            "account_id": cl.account_id,
            "credit_limit": float(cl.credit_limit),
            "current_balance": float(cl.current_balance),
            "annual_rate": float(cl.annual_rate),
            "available_credit": float(cl.credit_limit - cl.current_balance),
        }
        for cl in cls
    ]


@router.get("/credit-lines/{cl_id}", response_model=dict)
def get_cl(
    request: Request,
    cl_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        cl = get_credit_line(db, credit_line_id=cl_id, tenant_id=tenant_id)
    except LiabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    transactions = list_credit_line_transactions(db, credit_line_id=cl_id, tenant_id=tenant_id)
    return {
        "id": cl.id,
        "account_id": cl.account_id,
        "credit_limit": float(cl.credit_limit),
        "current_balance": float(cl.current_balance),
        "annual_rate": float(cl.annual_rate),
        "available_credit": float(cl.credit_limit - cl.current_balance),
        "transactions": [
            {
                "id": t.id,
                "date": t.date.isoformat(),
                "amount": float(t.amount),
                "type": t.type,
                "interest_charge": float(t.interest_charge),
            }
            for t in transactions
        ],
    }


@router.post("/credit-lines/{cl_id}/draw", response_model=dict)
def draw_cl(
    request: Request,
    cl_id: int,
    payload: CreditLineDraw,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        txn = credit_line_draw(
            db,
            credit_line_id=cl_id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            amount=Decimal(str(payload.amount)),
            draw_date=payload.draw_date,
        )
    except LiabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "date": txn.date.isoformat(),
        "amount": float(txn.amount),
        "type": txn.type,
    }


@router.post("/credit-lines/{cl_id}/payment", response_model=dict)
def pay_cl(
    request: Request,
    cl_id: int,
    payload: CreditLinePayment,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        txn = credit_line_payment(
            db,
            credit_line_id=cl_id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            amount=Decimal(str(payload.amount)),
            payment_date=payload.payment_date,
        )
    except LiabilityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "date": txn.date.isoformat(),
        "amount": float(txn.amount),
        "type": txn.type,
        "interest_charge": float(txn.interest_charge),
    }


@router.get("/credit-lines/{cl_id}/available")
def available_cl(
    request: Request,
    cl_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        available = credit_line_available(db, credit_line_id=cl_id, tenant_id=tenant_id)
    except LiabilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"credit_line_id": cl_id, "available_credit": float(available)}


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------

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