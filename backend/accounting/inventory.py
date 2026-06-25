"""Inventory & project tag domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


class InventoryError(Exception):
    """Domain error for inventory operations."""


def create_item(
    db: Session,
    tenant_id: int,
    user_id: int,
    sku: str,
    name: str,
    cogs_account_id: Optional[int] = None,
    income_account_id: Optional[int] = None,
    asset_account_id: Optional[int] = None,
    valuation_method: str = "average",
) -> models.InventoryItem:
    """Create an inventory item."""
    item = models.InventoryItem(
        tenant_id=tenant_id,
        user_id=user_id,
        sku=sku,
        name=name,
        cogs_account_id=cogs_account_id,
        income_account_id=income_account_id,
        asset_account_id=asset_account_id,
        valuation_method=valuation_method,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def adjust_inventory(
    db: Session,
    item_id: int,
    user_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    type_: str,  # purchase / sale / adjustment
) -> models.InventoryTransaction:
    """Record an inventory movement and update quantity on hand."""
    item = db.query(models.InventoryItem).filter(
        models.InventoryItem.id == item_id,
        models.InventoryItem.user_id == user_id,
    ).first()
    if item is None:
        raise InventoryError("Item not found")

    total = (qty * unit_cost).quantize(Decimal("0.01"))
    txn = models.InventoryTransaction(
        item_id=item_id,
        qty=qty,
        unit_cost=unit_cost,
        total_cost=total,
        type=type_,
    )
    db.add(txn)

    if type_ == "purchase":
        new_total = (item.qty_on_hand * item.unit_cost) + total
        new_qty = item.qty_on_hand + qty
        item.qty_on_hand = new_qty
        item.unit_cost = (new_total / new_qty).quantize(Decimal("0.0001")) if new_qty else Decimal("0")
    elif type_ == "sale":
        if qty > item.qty_on_hand:
            raise InventoryError("Not enough quantity on hand")
        item.qty_on_hand -= qty
    elif type_ == "adjustment":
        item.qty_on_hand = qty
    else:
        raise InventoryError("Invalid inventory transaction type")

    db.commit()
    db.refresh(txn)
    return txn


def list_items(db: Session, tenant_id: int, user_id: int) -> list[models.InventoryItem]:
    return db.query(models.InventoryItem).filter(
        models.InventoryItem.tenant_id == tenant_id,
        models.InventoryItem.user_id == user_id,
    ).order_by(models.InventoryItem.name).all()
