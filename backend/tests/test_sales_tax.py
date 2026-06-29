"""Tests for sales tax tracking (v3.11.6 R5)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account


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


def test_api_create_sales_tax_rate(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "name": "FL State",
        "jurisdiction": "FL",
        "rate": 0.06,
        "effective_date": "2026-01-01",
    }
    resp = auth_client.post("/api/sales-tax/rates", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["jurisdiction"] == "FL"
    assert body["rate"] == 0.06


def test_api_record_sales_tax_payment(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    # Create an asset account so the GL entry has a credit side.
    create_account(db, client.id, user.id, "1020", "Operating Checking", "asset")
    payload = {
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
        "payment_date": "2026-04-15",
        "amount": 250.00,
        "jurisdiction": "FL",
    }
    resp = auth_client.post("/api/sales-tax/payments", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["amount"] == 250.0
    assert body["jurisdiction"] == "FL"


def test_api_sales_tax_liability_summary(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
        "payment_date": "2026-04-15",
        "amount": 100.00,
        "jurisdiction": "FL",
    }
    resp = auth_client.post("/api/sales-tax/payments", json=payload)
    assert resp.status_code == 201
    resp = auth_client.get("/api/sales-tax/liability-summary?as_of=2026-12-31")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["remitted"] == 100.0
    assert body["balance"] == -100.0
