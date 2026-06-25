"""Investment lot API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.investments import (
    InvestmentError,
    add_lot,
    sell_lots_fifo,
    holdings,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/investments", tags=["investments"])


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


class LotCreate(BaseModel):
    account_id: int
    symbol: str
    shares: float
    cost_basis: float
    acquisition_date: date


class LotSell(BaseModel):
    symbol: str
    shares: float
    sale_date: date
    sale_price_per_share: float


@router.post("/lots", response_model=dict, status_code=201)
def create_lot(
    request: Request,
    payload: LotCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    lot = add_lot(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        account_id=payload.account_id,
        symbol=payload.symbol,
        shares=Decimal(str(payload.shares)),
        cost_basis=Decimal(str(payload.cost_basis)),
        acquisition_date=payload.acquisition_date,
    )
    return {
        "id": lot.id,
        "account_id": lot.account_id,
        "symbol": lot.symbol,
        "shares": float(lot.shares),
        "cost_basis": float(lot.cost_basis),
        "acquisition_date": lot.acquisition_date.isoformat(),
    }


@router.post("/{account_id}/sell", response_model=list[dict])
def sell_lots(
    request: Request,
    account_id: int,
    payload: LotSell,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    symbol = payload.symbol
    try:
        result = sell_lots_fifo(
            db,
            user_id=current_user.id,
            account_id=account_id,
            symbol=symbol,
            shares_to_sell=Decimal(str(payload.shares)),
            sale_date=payload.sale_date,
            sale_price_per_share=Decimal(str(payload.sale_price_per_share)),
        )
    except InvestmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/{account_id}/holdings")
def get_holdings(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    return holdings(db, user_id=current_user.id, account_id=account_id)
