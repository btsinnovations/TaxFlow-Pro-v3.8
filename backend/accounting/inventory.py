"""Inventory & project tag domain logic for TaxFlow Pro v3.11.

B3.03 — Full implementation:
- Inventory item CRUD.
- Inventory transactions: purchase, sale, adjustment.
- Valuation methods: FIFO and average cost.
- Project tags: free-form labels attached to transactions.
- Search/filter transactions by tag.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import models


class InventoryError(Exception):
    """Domain error for inventory operations."""


# ---------------------------------------------------------------------------
# Item CRUD
# ---------------------------------------------------------------------------

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
    if valuation_method not in ("fifo", "average"):
        raise InventoryError("Valuation method must be 'fifo' or 'average'")
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


def get_item(db: Session, item_id: int, tenant_id: int) -> models.InventoryItem:
    """Get an inventory item by ID, scoped to tenant."""
    item = db.query(models.InventoryItem).filter(
        models.InventoryItem.id == item_id,
        models.InventoryItem.tenant_id == tenant_id,
    ).first()
    if item is None:
        raise InventoryError("Item not found")
    return item


def update_item(
    db: Session,
    item_id: int,
    tenant_id: int,
    sku: Optional[str] = None,
    name: Optional[str] = None,
    cogs_account_id: Optional[int] = None,
    income_account_id: Optional[int] = None,
    asset_account_id: Optional[int] = None,
    valuation_method: Optional[str] = None,
) -> models.InventoryItem:
    """Update an inventory item."""
    item = get_item(db, item_id, tenant_id)
    if sku is not None:
        item.sku = sku
    if name is not None:
        item.name = name
    if cogs_account_id is not None:
        item.cogs_account_id = cogs_account_id
    if income_account_id is not None:
        item.income_account_id = income_account_id
    if asset_account_id is not None:
        item.asset_account_id = asset_account_id
    if valuation_method is not None:
        if valuation_method not in ("fifo", "average"):
            raise InventoryError("Valuation method must be 'fifo' or 'average'")
        item.valuation_method = valuation_method
    db.commit()
    db.refresh(item)
    return item


def list_items(db: Session, tenant_id: int, user_id: int) -> list[models.InventoryItem]:
    return db.query(models.InventoryItem).filter(
        models.InventoryItem.tenant_id == tenant_id,
        models.InventoryItem.user_id == user_id,
    ).order_by(models.InventoryItem.name).all()


# ---------------------------------------------------------------------------
# Inventory transactions (purchase / sale / adjustment)
# ---------------------------------------------------------------------------

def adjust_inventory(
    db: Session,
    item_id: int,
    user_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    type_: str,  # purchase / sale / adjustment
) -> models.InventoryTransaction:
    """Record an inventory movement and update quantity on hand.

    For 'average' valuation: updates unit_cost as weighted average.
    For 'fifo' valuation: unit_cost is the purchase cost; sales use
        the oldest purchase cost for COGS.
    """
    item = db.query(models.InventoryItem).filter(
        models.InventoryItem.id == item_id,
        models.InventoryItem.user_id == user_id,
    ).first()
    if item is None:
        raise InventoryError("Item not found")

    if type_ not in ("purchase", "sale", "adjustment"):
        raise InventoryError("Invalid inventory transaction type")

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
        if item.valuation_method == "average":
            new_total = (item.qty_on_hand * item.unit_cost) + total
            new_qty = item.qty_on_hand + qty
            item.qty_on_hand = new_qty
            item.unit_cost = (new_total / new_qty).quantize(Decimal("0.0001")) if new_qty else Decimal("0")
        else:  # fifo
            item.qty_on_hand += qty
            # unit_cost on item is not used for FIFO valuation of sales;
            # it's kept as the most recent purchase cost for reference.

    elif type_ == "sale":
        if qty > item.qty_on_hand:
            raise InventoryError("Not enough quantity on hand")
        if item.valuation_method == "fifo":
            # COGS = qty * oldest purchase cost
            cogs_per_unit = _fifo_cogs(db, item_id, qty)
            txn.unit_cost = cogs_per_unit
            txn.total_cost = (qty * cogs_per_unit).quantize(Decimal("0.01"))
        item.qty_on_hand -= qty

    elif type_ == "adjustment":
        item.qty_on_hand = qty
        if unit_cost > 0:
            item.unit_cost = unit_cost

    db.commit()
    db.refresh(txn)
    return txn


def _fifo_cogs(db: Session, item_id: int, qty: Decimal) -> Decimal:
    """Compute COGS using FIFO by looking at purchase transactions.

    Returns the weighted average cost of the oldest `qty` units purchased.
    """
    purchases = db.query(models.InventoryTransaction).filter(
        models.InventoryTransaction.item_id == item_id,
        models.InventoryTransaction.type == "purchase",
    ).order_by(models.InventoryTransaction.created_at).all()

    # Reconstruct FIFO layers from purchase history
    # Each purchase adds qty at unit_cost; sales consume from oldest
    layers = []
    for p in purchases:
        layers.append({"qty": Decimal(str(p.qty)), "unit_cost": Decimal(str(p.unit_cost))})

    # Consume from sales/adjustments
    sales = db.query(models.InventoryTransaction).filter(
        models.InventoryTransaction.item_id == item_id,
        models.InventoryTransaction.type == "sale",
    ).order_by(models.InventoryTransaction.created_at).all()

    for s in sales:
        remaining = Decimal(str(s.qty))
        for layer in layers:
            if remaining <= 0:
                break
            consume = min(layer["qty"], remaining)
            layer["qty"] -= consume
            remaining -= consume

    # Now consume qty from the front of the queue
    remaining = qty
    total_cost = Decimal("0")
    for layer in layers:
        if remaining <= 0:
            break
        consume = min(layer["qty"], remaining)
        total_cost += consume * layer["unit_cost"]
        layer["qty"] -= consume
        remaining -= consume

    if remaining > 0:
        # Not enough purchase history; use current item unit_cost as fallback
        item = db.query(models.InventoryItem).filter(
            models.InventoryItem.id == item_id,
        ).first()
        total_cost += remaining * (item.unit_cost if item else Decimal("0"))

    return (total_cost / qty).quantize(Decimal("0.0001")) if qty > 0 else Decimal("0")


def list_inventory_transactions(
    db: Session, item_id: int, tenant_id: int
) -> list[models.InventoryTransaction]:
    """List all inventory transactions for an item."""
    return db.query(models.InventoryTransaction).filter(
        models.InventoryTransaction.item_id == item_id,
    ).order_by(models.InventoryTransaction.created_at.desc()).all()


def inventory_valuation(
    db: Session,
    item_id: int,
    tenant_id: int,
) -> dict:
    """Calculate the current valuation of an inventory item."""
    item = get_item(db, item_id, tenant_id)
    if item.valuation_method == "average":
        value = (item.qty_on_hand * item.unit_cost).quantize(Decimal("0.01"))
    else:  # fifo
        # Use FIFO layers to compute total value
        purchases = db.query(models.InventoryTransaction).filter(
            models.InventoryTransaction.item_id == item_id,
            models.InventoryTransaction.type == "purchase",
        ).order_by(models.InventoryTransaction.created_at).all()

        layers = []
        for p in purchases:
            layers.append({"qty": Decimal(str(p.qty)), "unit_cost": Decimal(str(p.unit_cost))})

        sales = db.query(models.InventoryTransaction).filter(
            models.InventoryTransaction.item_id == item_id,
            models.InventoryTransaction.type == "sale",
        ).order_by(models.InventoryTransaction.created_at).all()

        for s in sales:
            remaining = Decimal(str(s.qty))
            for layer in layers:
                if remaining <= 0:
                    break
                consume = min(layer["qty"], remaining)
                layer["qty"] -= consume
                remaining -= consume

        value = sum(
            (layer["qty"] * layer["unit_cost"]).quantize(Decimal("0.01"))
            for layer in layers
            if layer["qty"] > 0
        )
        if not value:
            value = Decimal("0")

    return {
        "item_id": item_id,
        "sku": item.sku,
        "name": item.name,
        "valuation_method": item.valuation_method,
        "qty_on_hand": float(item.qty_on_hand),
        "unit_cost": float(item.unit_cost),
        "total_value": float(value),
    }


# ---------------------------------------------------------------------------
# Project tags
# ---------------------------------------------------------------------------

def add_tag(
    db: Session,
    tenant_id: int,
    user_id: int,
    transaction_id: int,
    tag: str,
) -> models.TransactionTag:
    """Add a project tag to a transaction."""
    # Verify transaction belongs to tenant
    txn = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.tenant_id == tenant_id,
    ).first()
    if txn is None:
        raise InventoryError("Transaction not found")

    # Check for duplicate
    existing = db.query(models.TransactionTag).filter(
        models.TransactionTag.transaction_id == transaction_id,
        models.TransactionTag.tag == tag,
    ).first()
    if existing is not None:
        return existing  # Idempotent

    tag_row = models.TransactionTag(
        transaction_id=transaction_id,
        tenant_id=tenant_id,
        user_id=user_id,
        tag=tag,
    )
    db.add(tag_row)
    db.commit()
    db.refresh(tag_row)
    return tag_row


def remove_tag(
    db: Session,
    tenant_id: int,
    transaction_id: int,
    tag: str,
) -> bool:
    """Remove a project tag from a transaction."""
    tag_row = db.query(models.TransactionTag).filter(
        models.TransactionTag.transaction_id == transaction_id,
        models.TransactionTag.tenant_id == tenant_id,
        models.TransactionTag.tag == tag,
    ).first()
    if tag_row is None:
        return False
    db.delete(tag_row)
    db.commit()
    return True


def list_tags_for_transaction(
    db: Session, tenant_id: int, transaction_id: int,
) -> list[str]:
    """List all tags for a transaction."""
    rows = db.query(models.TransactionTag).filter(
        models.TransactionTag.transaction_id == transaction_id,
        models.TransactionTag.tenant_id == tenant_id,
    ).all()
    return [r.tag for r in rows]


def search_by_tag(
    db: Session, tenant_id: int, tag: str,
) -> list[models.Transaction]:
    """Find all transactions with a given tag."""
    rows = db.query(models.TransactionTag).filter(
        models.TransactionTag.tenant_id == tenant_id,
        models.TransactionTag.tag == tag,
    ).all()
    txn_ids = [r.transaction_id for r in rows]
    if not txn_ids:
        return []
    return db.query(models.Transaction).filter(
        models.Transaction.id.in_(txn_ids),
        models.Transaction.tenant_id == tenant_id,
    ).order_by(models.Transaction.date.desc()).all()


def list_all_tags(db: Session, tenant_id: int) -> list[dict]:
    """List all unique tags for a tenant with counts."""
    rows = db.query(models.TransactionTag).filter(
        models.TransactionTag.tenant_id == tenant_id,
    ).all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.tag] = counts.get(r.tag, 0) + 1
    return [{"tag": tag, "count": count} for tag, count in sorted(counts.items())]