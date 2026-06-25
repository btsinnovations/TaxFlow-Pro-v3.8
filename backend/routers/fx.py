"""Multi-currency FX API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.fx import FXError, convert, set_rate
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


class FXRateCreate(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    effective_date: date


class FXConvert(BaseModel):
    amount: float
    from_currency: str
    to_currency: str
    as_of: date | None = None


@router.post("/rates", response_model=dict)
def create_rate(
    request: Request,
    payload: FXRateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    rate = set_rate(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        from_currency=payload.from_currency,
        to_currency=payload.to_currency,
        rate=Decimal(str(payload.rate)),
        effective_date=payload.effective_date,
    )
    return {
        "id": rate.id,
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "rate": float(rate.rate),
        "effective_date": rate.effective_date.isoformat(),
    }


@router.post("/convert", response_model=dict)
def convert_route(
    request: Request,
    payload: FXConvert,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        result = convert(
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
        "amount": payload.amount,
        "from_currency": payload.from_currency,
        "to_currency": payload.to_currency,
        "converted": float(result),
    }
