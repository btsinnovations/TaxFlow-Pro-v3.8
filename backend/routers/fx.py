from __future__ import annotations

from typing import Optional
"""Multi-currency FX API endpoints for TaxFlow Pro v3.11.

B3.04 — Full endpoints:
- POST   /fx/rates — create an FX rate
- GET    /fx/rates — list rates (with optional filters)
- POST   /fx/convert — convert amount (POST body)
- GET    /fx/convert — convert amount (query params)
- POST   /fx/transactions/{id}/foreign — attach foreign currency to a transaction
- POST   /fx/transactions/{id}/settle — calculate FX gain/loss on settlement
- GET    /fx/report — home-currency report of foreign transactions
"""

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.fx import (
    FXError,
    DEFAULT_HOME_CURRENCY,
    set_rate,
    list_rates,
    get_rate,
    convert,
    convert_with_details,
    attach_foreign_currency,
    calculate_fx_gain_loss,
    home_currency_report,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/fx", tags=["fx"])


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

class FXRateCreate(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    effective_date: date


class FXConvert(BaseModel):
    amount: float
    from_currency: str
    to_currency: str
    as_of: Optional[date] = None


class ForeignCurrencyAttach(BaseModel):
    foreign_amount: float
    foreign_currency: str


class FXSettle(BaseModel):
    settlement_date: date
    settlement_rate: Optional[float] = None


# ---------------------------------------------------------------------------
# Rate endpoints
# ---------------------------------------------------------------------------

@router.post("/rates", response_model=dict)
def create_rate(
    request: Request,
    payload: FXRateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        rate = set_rate(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            from_currency=payload.from_currency,
            to_currency=payload.to_currency,
            rate=Decimal(str(payload.rate)),
            effective_date=payload.effective_date,
        )
    except FXError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": rate.id,
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "rate": float(rate.rate),
        "effective_date": rate.effective_date.isoformat(),
        "source": rate.source,
    }


@router.get("/rates", response_model=list[dict])
def get_rates(
    request: Request,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    rates = list_rates(db, tenant_id=tenant_id, from_currency=from_currency, to_currency=to_currency)
    return [
        {
            "id": r.id,
            "from_currency": r.from_currency,
            "to_currency": r.to_currency,
            "rate": float(r.rate),
            "effective_date": r.effective_date.isoformat(),
            "source": r.source,
        }
        for r in rates
    ]


# ---------------------------------------------------------------------------
# Convert endpoints
# ---------------------------------------------------------------------------

@router.post("/convert", response_model=dict)
def convert_route(
    request: Request,
    payload: FXConvert,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        result = convert_with_details(
            db,
            tenant_id=tenant_id,
            foreign_amount=Decimal(str(payload.amount)),
            from_currency=payload.from_currency,
            to_currency=payload.to_currency,
            as_of=payload.as_of,
        )
    except FXError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "from_currency": result["from_currency"],
        "to_currency": result["to_currency"],
        "rate": float(result["rate"]),
        "amount": float(result["amount"]),
        "converted": float(result["converted"]),
        "effective_date": result["effective_date"],
    }


@router.get("/convert", response_model=dict)
def convert_get(
    request: Request,
    from_currency: str = Query(..., alias="from"),
    to_currency: str = Query(..., alias="to"),
    amount: float = Query(...),
    as_of: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        result = convert_with_details(
            db,
            tenant_id=tenant_id,
            foreign_amount=Decimal(str(amount)),
            from_currency=from_currency,
            to_currency=to_currency,
            as_of=as_of,
        )
    except FXError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "from_currency": result["from_currency"],
        "to_currency": result["to_currency"],
        "rate": float(result["rate"]),
        "amount": float(result["amount"]),
        "converted": float(result["converted"]),
        "effective_date": result["effective_date"],
    }


# ---------------------------------------------------------------------------
# Transaction foreign currency endpoints
# ---------------------------------------------------------------------------

@router.post("/transactions/{transaction_id}/foreign", response_model=dict)
def attach_foreign(
    request: Request,
    transaction_id: int,
    payload: ForeignCurrencyAttach,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        txn = attach_foreign_currency(
            db,
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            foreign_amount=Decimal(str(payload.foreign_amount)),
            foreign_currency=payload.foreign_currency,
        )
    except FXError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "foreign_amount": float(txn.foreign_amount),
        "foreign_currency": txn.foreign_currency,
        "fx_rate_snapshot": float(txn.fx_rate_snapshot),
        "home_amount": float(txn.amount),
    }


@router.post("/transactions/{transaction_id}/settle", response_model=dict)
def settle_fx(
    request: Request,
    transaction_id: int,
    payload: FXSettle,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        result = calculate_fx_gain_loss(
            db,
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            settlement_date=payload.settlement_date,
            settlement_rate=Decimal(str(payload.settlement_rate)) if payload.settlement_rate else None,
        )
    except FXError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


# ---------------------------------------------------------------------------
# Report endpoint
# ---------------------------------------------------------------------------

@router.get("/report", response_model=dict)
def fx_report(
    request: Request,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    return home_currency_report(db, tenant_id=tenant_id, start_date=start_date, end_date=end_date)