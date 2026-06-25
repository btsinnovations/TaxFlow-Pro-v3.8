"""Inventory & project tags API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.inventory import InventoryError, create_item, adjust_inventory, list_items
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/inventory", tags=["inventory"])


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


class ItemCreate(BaseModel):
    sku: str
    name: str
    cogs_account_id: int | None = None
    income_account_id: int | None = None
    asset_account_id: int | None = None
    valuation_method: str = "average"


class Adjustment(BaseModel):
    qty: float
    unit_cost: float
    type: str  # purchase / sale / adjustment


@router.get("/", response_model=list[dict])
def get_items(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    rows = list_items(db, tenant_id=tenant_id, user_id=current_user.id)
    return [
        {
            "id": i.id,
            "sku": i.sku,
            "name": i.name,
            "qty_on_hand": float(i.qty_on_hand),
            "unit_cost": float(i.unit_cost),
            "valuation_method": i.valuation_method,
        }
        for i in rows
    ]


@router.post("/", response_model=dict, status_code=201)
def create_item_route(
    request: Request,
    payload: ItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    item = create_item(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        sku=payload.sku,
        name=payload.name,
        cogs_account_id=payload.cogs_account_id,
        income_account_id=payload.income_account_id,
        asset_account_id=payload.asset_account_id,
        valuation_method=payload.valuation_method,
    )
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "qty_on_hand": float(item.qty_on_hand),
        "unit_cost": float(item.unit_cost),
    }


@router.post("/{item_id}/adjust", response_model=dict)
def adjust(
    request: Request,
    item_id: int,
    payload: Adjustment,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    try:
        txn = adjust_inventory(
            db,
            item_id=item_id,
            user_id=current_user.id,
            qty=Decimal(str(payload.qty)),
            unit_cost=Decimal(str(payload.unit_cost)),
            type_=payload.type,
        )
    except InventoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": txn.id,
        "qty": float(txn.qty),
        "unit_cost": float(txn.unit_cost),
        "total_cost": float(txn.total_cost),
        "type": txn.type,
    }
