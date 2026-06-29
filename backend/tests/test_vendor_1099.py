"""Tests for vendor-keyed 1099 reporting (v3.11.6 R5)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account
from backend.accounting.tax_exports import form_1099_nec_misc


def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Auth Tax Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def test_vendor_1099_over_threshold(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    vendor = models.Vendor(
        tenant_id=client.id,
        user_id=user.id,
        name="ABC Contractor",
        tax_id="12-3456789",
        is_1099_eligible=True,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    # Need an asset account for sales-tax GL, not used here but create_invoice may post.
    create_account(db, client.id, user.id, "1020", "Operating Checking", "asset")
    bill_payload = {
        "contact_name": "ABC Contractor",
        "invoice_number": "BILL-001",
        "issue_date": "2026-05-01",
        "due_date": "2026-06-01",
        "line_items": [{"description": "Consulting", "qty": 1, "rate": 700.00}],
    }
    resp = auth_client.post("/api/invoicing/bills", json=bill_payload)
    assert resp.status_code == 201, resp.text
    bill_id = resp.json()["id"]

    payment_payload = {"amount": 700.00, "payment_date": "2026-05-15", "method": "manual"}
    resp = auth_client.post(f"/api/invoicing/{bill_id}/payments", json=payment_payload)
    assert resp.status_code == 200, resp.text

    results = form_1099_nec_misc(db, client.id, user.id, 2026, threshold=Decimal("600"))
    assert len(results) == 1
    assert results[0]["payee"] == "ABC Contractor"
    assert results[0]["vendor_id"] == vendor.id
    assert results[0]["form"] == "1099-NEC"
    assert results[0]["amount"] == 700.0
    assert results[0]["tin"] == "12-3456789"


def test_vendor_1099_under_threshold_excluded(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    vendor = models.Vendor(
        tenant_id=client.id,
        user_id=user.id,
        name="Small Supplier",
        is_1099_eligible=True,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    create_account(db, client.id, user.id, "1021", "Operating Checking 2", "asset")
    bill_payload = {
        "contact_name": "Small Supplier",
        "invoice_number": "BILL-002",
        "issue_date": "2026-05-01",
        "due_date": "2026-06-01",
        "line_items": [{"description": "Supplies", "qty": 1, "rate": 500.00}],
    }
    resp = auth_client.post("/api/invoicing/bills", json=bill_payload)
    assert resp.status_code == 201
    bill_id = resp.json()["id"]

    payment_payload = {"amount": 500.00, "payment_date": "2026-05-15", "method": "manual"}
    resp = auth_client.post(f"/api/invoicing/{bill_id}/payments", json=payment_payload)
    assert resp.status_code == 200

    results = form_1099_nec_misc(db, client.id, user.id, 2026, threshold=Decimal("600"))
    assert all(r["payee"] != "Small Supplier" for r in results)
