"""Investment lot API endpoints for TaxFlow Pro v3.11.

B3.02 — Full endpoints:
- POST /investments/lots — create a lot (buy)
- POST /investments/{account_id}/sell — sell with FIFO
- GET  /investments/{account_id}/holdings — current holdings
- GET  /investments/{account_id}/unrealized — unrealized gains
- GET  /investments/{account_id}/cost-basis — cost-basis report
- POST /investments/{account_id}/dividend — record dividend
- POST /investments/{account_id}/split — record stock split
- POST /investments/prices — add price snapshot
- GET  /investments/{account_id}/events — list investment events
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
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
    record_dividend,
    record_split,
    add_price_snapshot,
    unrealized_gains,
    cost_basis_report,
    list_events,
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

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


class DividendRequest(BaseModel):
    symbol: str
    ex_date: date
    amount: float
    shares: float = 0
    description: str | None = None


class SplitRequest(BaseModel):
    symbol: str
    split_date: date
    split_ratio: str


class PriceSnapshotRequest(BaseModel):
    symbol: str
    price: float
    snapshot_date: date
    source: str = "manual"


# ---------------------------------------------------------------------------
# Lot endpoints
# ---------------------------------------------------------------------------

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
    try:
        result = sell_lots_fifo(
            db,
            user_id=current_user.id,
            account_id=account_id,
            symbol=payload.symbol,
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


# ---------------------------------------------------------------------------
# Dividend & Split endpoints
# ---------------------------------------------------------------------------

@router.post("/{account_id}/dividend", response_model=dict)
def record_dividend_event(
    request: Request,
    account_id: int,
    payload: DividendRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    event = record_dividend(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        account_id=account_id,
        symbol=payload.symbol,
        ex_date=payload.ex_date,
        amount=Decimal(str(payload.amount)),
        shares=Decimal(str(payload.shares)),
        description=payload.description,
    )
    return {
        "id": event.id,
        "symbol": event.symbol,
        "event_type": event.event_type,
        "event_date": event.event_date.isoformat(),
        "amount": float(event.amount),
    }


@router.post("/{account_id}/split", response_model=dict)
def record_split_event(
    request: Request,
    account_id: int,
    payload: SplitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        event = record_split(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            account_id=account_id,
            symbol=payload.symbol,
            split_date=payload.split_date,
            split_ratio=payload.split_ratio,
        )
    except InvestmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": event.id,
        "symbol": event.symbol,
        "event_type": event.event_type,
        "event_date": event.event_date.isoformat(),
        "split_ratio": event.split_ratio,
    }


# ---------------------------------------------------------------------------
# Price snapshot endpoints
# ---------------------------------------------------------------------------

@router.post("/prices", response_model=dict, status_code=201)
def add_price(
    request: Request,
    payload: PriceSnapshotRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    snapshot = add_price_snapshot(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        symbol=payload.symbol,
        price=Decimal(str(payload.price)),
        snapshot_date=payload.snapshot_date,
        source=payload.source,
    )
    return {
        "id": snapshot.id,
        "symbol": snapshot.symbol,
        "price": float(snapshot.price),
        "snapshot_date": snapshot.snapshot_date.isoformat(),
    }


# ---------------------------------------------------------------------------
# Reporting endpoints
# ---------------------------------------------------------------------------

@router.get("/{account_id}/unrealized")
def get_unrealized(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    as_of: date | None = None,
):
    _wrap_tenant(request, db, current_user)
    return unrealized_gains(db, user_id=current_user.id, account_id=account_id, as_of=as_of)


@router.get("/{account_id}/cost-basis")
def get_cost_basis(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    year: int | None = None,
):
    _wrap_tenant(request, db, current_user)
    return cost_basis_report(db, user_id=current_user.id, account_id=account_id, year=year)


@router.get("/{account_id}/events")
def get_events(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    symbol: str | None = None,
):
    tenant_id = _wrap_tenant(request, db, current_user)
    events = list_events(db, tenant_id=tenant_id, account_id=account_id, symbol=symbol)
    return [
        {
            "id": ev.id,
            "symbol": ev.symbol,
            "event_type": ev.event_type,
            "event_date": ev.event_date.isoformat(),
            "shares": float(ev.shares),
            "amount": float(ev.amount),
            "split_ratio": ev.split_ratio,
            "description": ev.description,
        }
        for ev in events
    ]