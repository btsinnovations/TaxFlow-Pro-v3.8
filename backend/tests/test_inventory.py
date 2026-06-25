"""Tests for the v3.11 Inventory module."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.inventory import InventoryError, adjust_inventory, create_item, list_items


def _seed_user(db: Session):
    from backend.routers.auth import get_password_hash

    user = db.query(models.User).filter(models.User.username == "invtest").first()
    if user:
        db.delete(user)
        db.commit()

    user = models.User(
        username="invtest",
        email="invtest@example.com",
        hashed_password=get_password_hash("P4ssw0rd!"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="Inv Test Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------

def test_create_inventory_item(db: Session):
    user, client = _seed_user(db)
    item = create_item(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        sku="WIDGET-01",
        name="Widget",
    )
    assert item.id is not None
    assert item.sku == "WIDGET-01"
    assert item.name == "Widget"
    assert item.qty_on_hand == Decimal("0")
    assert item.unit_cost == Decimal("0")
    assert item.valuation_method == "average"


def test_purchase_updates_average_cost(db: Session):
    user, client = _seed_user(db)
    item = create_item(db, client.id, user.id, "WIDGET-02", "Widget Two")

    adjust_inventory(db, item.id, user.id, Decimal("10"), Decimal("5.00"), "purchase")
    db.refresh(item)
    assert item.qty_on_hand == Decimal("10")
    assert item.unit_cost == Decimal("5.0000")

    adjust_inventory(db, item.id, user.id, Decimal("10"), Decimal("7.00"), "purchase")
    db.refresh(item)
    assert item.qty_on_hand == Decimal("20")
    assert item.unit_cost == Decimal("6.0000")


def test_sale_reduces_quantity(db: Session):
    user, client = _seed_user(db)
    item = create_item(db, client.id, user.id, "WIDGET-03", "Widget Three")
    adjust_inventory(db, item.id, user.id, Decimal("10"), Decimal("5.00"), "purchase")
    adjust_inventory(db, item.id, user.id, Decimal("3"), Decimal("5.00"), "sale")
    db.refresh(item)
    assert item.qty_on_hand == Decimal("7")


def test_sale_without_inventory_fails(db: Session):
    user, client = _seed_user(db)
    item = create_item(db, client.id, user.id, "WIDGET-04", "Widget Four")
    with pytest.raises(InventoryError, match="Not enough quantity"):
        adjust_inventory(db, item.id, user.id, Decimal("1"), Decimal("5.00"), "sale")


def test_adjustment_overwrites_quantity(db: Session):
    user, client = _seed_user(db)
    item = create_item(db, client.id, user.id, "WIDGET-05", "Widget Five")
    adjust_inventory(db, item.id, user.id, Decimal("5"), Decimal("4.00"), "purchase")
    adjust_inventory(db, item.id, user.id, Decimal("12"), Decimal("4.00"), "adjustment")
    db.refresh(item)
    assert item.qty_on_hand == Decimal("12")


def test_list_items_filters_by_user_and_tenant(db: Session):
    user_a, client_a = _seed_user(db)
    item_a = create_item(db, client_a.id, user_a.id, "A", "Item A")

    user_b = models.User(
        username="invtest_b",
        email="b@example.com",
        hashed_password="fakehash",
        is_active=True,
    )
    db.add(user_b)
    db.commit()
    db.refresh(user_b)
    client_b = models.Client(name="Client B", user_id=user_b.id)
    db.add(client_b)
    db.commit()
    db.refresh(client_b)
    item_b = create_item(db, client_b.id, user_b.id, "B", "Item B")

    items_for_a = list_items(db, tenant_id=client_a.id, user_id=user_a.id)
    assert len(items_for_a) == 1
    assert items_for_a[0].id == item_a.id


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Inv Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def test_api_create_inventory_item(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {"sku": "API-WIDGET", "name": "API Widget"}
    resp = auth_client.post("/api/inventory/", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["sku"] == "API-WIDGET"
    assert body["qty_on_hand"] == 0.0


def test_api_adjust_purchase_and_sale(auth_client: TestClient, db: Session):
    _, client = _ensure_auth_user(db)
    item = create_item(db, client.id, client.user_id, "API-ADJ", "API Adjustment")

    resp = auth_client.post(f"/api/inventory/{item.id}/adjust", json={
        "qty": 10.0,
        "unit_cost": 5.0,
        "type": "purchase",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["type"] == "purchase"

    resp = auth_client.post(f"/api/inventory/{item.id}/adjust", json={
        "qty": 2.0,
        "unit_cost": 5.0,
        "type": "sale",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["type"] == "sale"

    resp = auth_client.get("/api/inventory/")
    assert resp.status_code == 200
    item_data = next(i for i in resp.json() if i["id"] == item.id)
    assert item_data["qty_on_hand"] == 8.0


def test_api_sale_without_inventory_fails(auth_client: TestClient, db: Session):
    _, client = _ensure_auth_user(db)
    item = create_item(db, client.id, client.user_id, "API-NOQTY", "No Qty")
    resp = auth_client.post(f"/api/inventory/{item.id}/adjust", json={
        "qty": 1.0,
        "unit_cost": 5.0,
        "type": "sale",
    })
    assert resp.status_code == 400
    assert "Not enough quantity" in resp.json()["detail"]
