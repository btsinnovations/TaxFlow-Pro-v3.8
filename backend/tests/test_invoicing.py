"""Tests for the v3.11 Invoicing / A/P / A/R module."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.invoicing import (
    InvoicingError,
    aging_report,
    create_bill,
    create_invoice,
    delete_invoice,
    get_invoice,
    list_invoices,
    record_payment,
    reverse_payment,
    update_invoice,
    void_invoice,
)


def _seed_user_and_tenant(db: Session):
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

    client = models.Client(name="Invoicing Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client


# ---------------------------------------------------------------------------
# Domain tests
# ---------------------------------------------------------------------------

def test_create_invoice(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        contact_name="Acme Co",
        invoice_number="INV-001",
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 2, 1),
        line_items=[
            {"description": "Service A", "qty": 2, "rate": 100.0},
            {"description": "Service B", "qty": 1, "rate": 50.0},
        ],
    )
    assert invoice.id is not None
    assert invoice.total == Decimal("250.00")
    assert invoice.is_bill is False
    assert invoice.status == "open"
    assert invoice.amount_paid == Decimal("0.00")


def test_create_bill(db: Session):
    user, client = _seed_user_and_tenant(db)
    bill = create_bill(
        db=db,
        tenant_id=client.id,
        user_id=user.id,
        contact_name="Vendor Inc",
        invoice_number="BILL-001",
        issue_date=date(2026, 1, 10),
        due_date=date(2026, 2, 10),
        line_items=[{"description": "Materials", "qty": 5, "rate": 20.0}],
    )
    assert bill.id is not None
    assert bill.total == Decimal("100.00")
    assert bill.is_bill is True
    assert bill.status == "open"


def test_record_payment_partial(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Client", "INV-002", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "Service", "qty": 1, "rate": 300.0}],
    )
    updated = record_payment(
        db, invoice.id, user.id, Decimal("100.00"), date(2026, 1, 15),
    )
    assert updated.amount_paid == Decimal("100.00")
    assert updated.status == "open"


def test_record_payment_full(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Client", "INV-003", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "Service", "qty": 1, "rate": 200.0}],
    )
    updated = record_payment(
        db, invoice.id, user.id, Decimal("200.00"), date(2026, 1, 20),
    )
    assert updated.amount_paid == Decimal("200.00")
    assert updated.status == "paid"


def test_over_payment_fails(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Client", "INV-004", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "Service", "qty": 1, "rate": 150.0}],
    )
    with pytest.raises(InvoicingError, match="exceeds outstanding balance"):
        record_payment(db, invoice.id, user.id, Decimal("200.00"), date(2026, 1, 15))


def test_aging_report_buckets(db: Session):
    user, client = _seed_user_and_tenant(db)
    today = date.today()

    # Current bucket
    create_invoice(
        db, client.id, user.id, "Current", "INV-C", today, today + timedelta(days=15),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    # 30 days bucket
    create_invoice(
        db, client.id, user.id, "30", "INV-30", today, today - timedelta(days=10),
        [{"description": "X", "qty": 1, "rate": 200.0}],
    )
    # 60 days bucket
    create_invoice(
        db, client.id, user.id, "60", "INV-60", today, today - timedelta(days=45),
        [{"description": "X", "qty": 1, "rate": 300.0}],
    )
    # 90+ days bucket, paid (excluded)
    paid = create_invoice(
        db, client.id, user.id, "Paid", "INV-P", today, today - timedelta(days=100),
        [{"description": "X", "qty": 1, "rate": 500.0}],
    )
    record_payment(db, paid.id, user.id, Decimal("500.00"), today)

    report = aging_report(db, user.id, is_bill=False)
    buckets = report["buckets"]
    assert buckets["current"] == 100.0
    assert buckets["30"] == 200.0
    assert buckets["60"] == 300.0
    assert buckets["90+"] == 0.0
    assert report["count"] == 3


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert auth_user is not None
    if not auth_user.clients:
        client = models.Client(name="Invoicing Auth Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    return auth_user, auth_user.clients[0]


def test_api_create_invoice(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "contact_name": "API Client",
        "invoice_number": "API-INV-001",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-31",
        "line_items": [
            {"description": "Consulting", "qty": 3, "rate": 100.0},
        ],
    }
    resp = auth_client.post("/api/invoicing/invoices", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["total"] == 300.0
    assert body["status"] == "open"


def test_api_create_bill(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "contact_name": "API Vendor",
        "invoice_number": "API-BILL-001",
        "issue_date": "2026-03-01",
        "due_date": "2026-03-31",
        "line_items": [
            {"description": "Rent", "qty": 1, "rate": 800.0},
        ],
    }
    resp = auth_client.post("/api/invoicing/bills", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["total"] == 800.0
    assert body["is_bill"] is True


def test_api_record_payment(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "Pay Client", "API-PAY-001",
        date(2026, 4, 1), date(2026, 5, 1),
        [{"description": "Service", "qty": 1, "rate": 400.0}],
    )
    payload = {"amount": 400.0, "payment_date": "2026-04-10", "method": "check"}
    resp = auth_client.post(f"/api/invoicing/{invoice.id}/payments", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["amount_paid"] == 400.0
    assert body["status"] == "paid"


def test_api_over_payment_fails(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "Overpay", "API-OP-001",
        date(2026, 4, 1), date(2026, 5, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    payload = {"amount": 200.0, "payment_date": "2026-04-10"}
    resp = auth_client.post(f"/api/invoicing/{invoice.id}/payments", json=payload)
    assert resp.status_code == 400
    assert "exceeds outstanding balance" in resp.json()["detail"]


def test_api_aging_report(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    today = date.today()
    create_invoice(
        db, client.id, auth_user.id, "Aging", "API-AGING-001",
        today, today - timedelta(days=20),
        [{"description": "X", "qty": 1, "rate": 250.0}],
    )
    resp = auth_client.get("/api/invoicing/aging")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["buckets"]["30"] == 250.0


# ---------------------------------------------------------------------------
# Expanded domain tests
# ---------------------------------------------------------------------------

def test_void_invoice(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "VoidMe", "INV-VOID", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    voided = void_invoice(db, invoice.id, user.id)
    assert voided.status == "void"


def test_void_already_voided_fails(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "VoidTwice", "INV-VOID2", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    void_invoice(db, invoice.id, user.id)
    with pytest.raises(InvoicingError, match="already voided"):
        void_invoice(db, invoice.id, user.id)


def test_payment_on_void_fails(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "VoidPay", "INV-VP", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    void_invoice(db, invoice.id, user.id)
    with pytest.raises(InvoicingError, match="void invoice"):
        record_payment(db, invoice.id, user.id, Decimal("50.00"), date(2026, 1, 15))


def test_reverse_payment(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Reverse", "INV-REV", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 200.0}],
    )
    record_payment(db, invoice.id, user.id, Decimal("200.00"), date(2026, 1, 10))
    assert invoice.status == "paid"
    payment_id = invoice.payments[0].id
    updated = reverse_payment(db, invoice.id, payment_id, user.id)
    assert updated.amount_paid == Decimal("0.00")
    assert updated.status in ("open", "overdue")


def test_reverse_payment_not_found(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "NoRev", "INV-NR", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    with pytest.raises(InvoicingError, match="Payment not found"):
        reverse_payment(db, invoice.id, 99999, user.id)


def test_delete_invoice_draft(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Delete", "INV-DEL", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 50.0}],
    )
    assert delete_invoice(db, invoice.id, user.id) is True
    assert get_invoice(db, invoice.id, user.id) is None


def test_delete_invoice_with_payment_fails(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "NoDelete", "INV-ND", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    record_payment(db, invoice.id, user.id, Decimal("100.00"), date(2026, 1, 10))
    # Invoice is now 'paid' — delete should fail on status check
    with pytest.raises(InvoicingError, match="Cannot delete invoice in 'paid' status"):
        delete_invoice(db, invoice.id, user.id)


def test_update_invoice_line_items(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Update", "INV-UPD", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "Old", "qty": 1, "rate": 100.0}],
    )
    updated = update_invoice(
        db, invoice.id, user.id,
        line_items=[
            {"description": "New A", "qty": 2, "rate": 50.0},
            {"description": "New B", "qty": 1, "rate": 25.0},
        ],
    )
    assert updated.total == Decimal("125.00")
    assert len(updated.line_items) == 2


def test_update_invoice_contact(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "OldName", "INV-CN", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    updated = update_invoice(db, invoice.id, user.id, contact_name="NewName")
    assert updated.contact_name == "NewName"


def test_list_invoices_status_filter(db: Session):
    user, client = _seed_user_and_tenant(db)
    create_invoice(
        db, client.id, user.id, "Open", "INV-F1", date(2026, 1, 1), date(2026, 3, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    inv2 = create_invoice(
        db, client.id, user.id, "Paid", "INV-F2", date(2026, 1, 1), date(2026, 3, 1),
        [{"description": "X", "qty": 1, "rate": 200.0}],
    )
    record_payment(db, inv2.id, user.id, Decimal("200.00"), date(2026, 1, 10))
    open_only = list_invoices(db, user.id, is_bill=False, status="open")
    paid_only = list_invoices(db, user.id, is_bill=False, status="paid")
    assert all(r["status"] == "open" for r in open_only)
    assert all(r["status"] == "paid" for r in paid_only)
    assert any(r["invoice_number"] == "INV-F1" for r in open_only)
    assert any(r["invoice_number"] == "INV-F2" for r in paid_only)


def test_negative_payment_fails(db: Session):
    user, client = _seed_user_and_tenant(db)
    invoice = create_invoice(
        db, client.id, user.id, "Neg", "INV-NEG", date(2026, 1, 1), date(2026, 2, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    with pytest.raises(InvoicingError, match="positive"):
        record_payment(db, invoice.id, user.id, Decimal("-50.00"), date(2026, 1, 10))


# ---------------------------------------------------------------------------
# Expanded API tests
# ---------------------------------------------------------------------------

def test_api_get_single_invoice(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "Single", "API-SINGLE-001",
        date(2026, 5, 1), date(2026, 6, 1),
        [{"description": "Service", "qty": 1, "rate": 300.0}],
    )
    resp = auth_client.get(f"/api/invoicing/{invoice.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == invoice.id
    assert body["total"] == 300.0
    assert len(body["line_items"]) == 1


def test_api_void_invoice(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "VoidAPI", "API-VOID-001",
        date(2026, 5, 1), date(2026, 6, 1),
        [{"description": "X", "qty": 1, "rate": 150.0}],
    )
    resp = auth_client.post(f"/api/invoicing/{invoice.id}/void")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "void"


def test_api_delete_invoice(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "DelAPI", "API-DEL-001",
        date(2026, 5, 1), date(2026, 6, 1),
        [{"description": "X", "qty": 1, "rate": 75.0}],
    )
    resp = auth_client.delete(f"/api/invoicing/{invoice.id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True


def test_api_reverse_payment(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "RevAPI", "API-REV-001",
        date(2026, 5, 1), date(2026, 6, 1),
        [{"description": "X", "qty": 1, "rate": 250.0}],
    )
    pay_resp = auth_client.post(f"/api/invoicing/{invoice.id}/payments", json={
        "amount": 250.0, "payment_date": "2026-05-10",
    })
    assert pay_resp.status_code == 200
    payment_id = invoice.payments[0].id
    resp = auth_client.delete(f"/api/invoicing/{invoice.id}/payments/{payment_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["amount_paid"] == 0.0
    assert body["status"] in ("open", "overdue")


def test_api_list_invoices_with_filter(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    create_invoice(
        db, client.id, auth_user.id, "Filter", "API-FILT-001",
        date(2026, 5, 1), date(2026, 6, 1),
        [{"description": "X", "qty": 1, "rate": 100.0}],
    )
    resp = auth_client.get("/api/invoicing/invoices", params={"status": "open"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(r["status"] == "open" for r in body)


def test_api_update_invoice(auth_client: TestClient, db: Session):
    auth_user, client = _ensure_auth_user(db)
    invoice = create_invoice(
        db, client.id, auth_user.id, "UpdAPI", "API-UPD-001",
        date(2026, 5, 1), date(2026, 6, 1),
        [{"description": "Old", "qty": 1, "rate": 100.0}],
    )
    resp = auth_client.put(f"/api/invoicing/{invoice.id}", json={
        "contact_name": "Updated Contact",
        "line_items": [
            {"description": "New", "qty": 2, "rate": 50.0}
        ],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 100.0
