"""Inventory & project tags API endpoints for TaxFlow Pro v3.11.

B3.03 — Full endpoints:
- GET  /inventory/ — list items
- POST /inventory/ — create item
- GET  /inventory/{id} — get item
- PUT  /inventory/{id} — update item
- POST /inventory/{id}/adjust — purchase / sale / adjustment
- GET  /inventory/{id}/transactions — list inventory txns
- GET  /inventory/{id}/valuation — current valuation
- POST /inventory/tags/{transaction_id} — add tag to transaction
- DELETE /inventory/tags/{transaction_id} — remove tag
- GET  /inventory/tags — list all tags
- GET  /inventory/tags/search?tag=... — search transactions by tag
"""
from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.inventory import (
    InventoryError,
    create_item,
    get_item,
    update_item,
    adjust_inventory,
    list_items,
    list_inventory_transactions,
    inventory_valuation,
    add_tag,
    remove_tag,
    list_tags_for_transaction,
    search_by_tag,
    list_all_tags,
)
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ItemCreate(BaseModel):
    sku: str
    name: str
    cogs_account_id: int | None = None
    income_account_id: int | None = None
    asset_account_id: int | None = None
    valuation_method: str = "average"


class ItemUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    cogs_account_id: int | None = None
    income_account_id: int | None = None
    asset_account_id: int | None = None
    valuation_method: str | None = None


class Adjustment(BaseModel):
    qty: float
    unit_cost: float
    type: str  # purchase / sale / adjustment


class TagAdd(BaseModel):
    tag: str


# ---------------------------------------------------------------------------
# Item endpoints
# ---------------------------------------------------------------------------

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
    try:
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
    except InventoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "qty_on_hand": float(item.qty_on_hand),
        "unit_cost": float(item.unit_cost),
        "valuation_method": item.valuation_method,
    }


@router.get("/{item_id}", response_model=dict)
def get_item_route(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        item = get_item(db, item_id=item_id, tenant_id=tenant_id)
    except InventoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "qty_on_hand": float(item.qty_on_hand),
        "unit_cost": float(item.unit_cost),
        "valuation_method": item.valuation_method,
    }


@router.put("/{item_id}", response_model=dict)
def update_item_route(
    request: Request,
    item_id: int,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        item = update_item(
            db,
            item_id=item_id,
            tenant_id=tenant_id,
            sku=payload.sku,
            name=payload.name,
            cogs_account_id=payload.cogs_account_id,
            income_account_id=payload.income_account_id,
            asset_account_id=payload.asset_account_id,
            valuation_method=payload.valuation_method,
        )
    except InventoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "qty_on_hand": float(item.qty_on_hand),
        "unit_cost": float(item.unit_cost),
        "valuation_method": item.valuation_method,
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


@router.get("/{item_id}/transactions", response_model=list[dict])
def get_item_transactions(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    txns = list_inventory_transactions(db, item_id=item_id, tenant_id=tenant_id)
    return [
        {
            "id": t.id,
            "qty": float(t.qty),
            "unit_cost": float(t.unit_cost),
            "total_cost": float(t.total_cost),
            "type": t.type,
        }
        for t in txns
    ]


@router.get("/{item_id}/valuation", response_model=dict)
def get_valuation(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        return inventory_valuation(db, item_id=item_id, tenant_id=tenant_id)
    except InventoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Project tag endpoints
# ---------------------------------------------------------------------------

@router.post("/tags/{transaction_id}", response_model=dict)
def add_tag_route(
    request: Request,
    transaction_id: int,
    payload: TagAdd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    try:
        tag = add_tag(
            db,
            tenant_id=tenant_id,
            user_id=current_user.id,
            transaction_id=transaction_id,
            tag=payload.tag,
        )
    except InventoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": tag.id, "transaction_id": tag.transaction_id, "tag": tag.tag}


@router.delete("/tags/{transaction_id}", response_model=dict)
def remove_tag_route(
    request: Request,
    transaction_id: int,
    tag: str = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    removed = remove_tag(db, tenant_id=tenant_id, transaction_id=transaction_id, tag=tag)
    if not removed:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"ok": True}


@router.get("/tags", response_model=list[dict])
def list_tags(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    return list_all_tags(db, tenant_id=tenant_id)


@router.get("/tags/search", response_model=list[dict])
def search_tags(
    request: Request,
    tag: str = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    txns = search_by_tag(db, tenant_id=tenant_id, tag=tag)
    return [
        {
            "id": t.id,
            "date": t.date.isoformat() if t.date else None,
            "description": t.description,
            "amount": float(t.amount) if t.amount is not None else None,
            "tx_type": t.tx_type,
        }
        for t in txns
    ]