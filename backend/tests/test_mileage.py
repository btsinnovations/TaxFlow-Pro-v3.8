"""Tests for mileage log (v3.11.6 R5)."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models


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


def test_api_create_mileage_log(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "trip_date": "2026-04-01",
        "description": "Client visit",
        "starting_odometer": 1000.0,
        "ending_odometer": 1050.0,
        "purpose": "business",
        "vehicle": "Honda Civic",
        "reimbursement_rate": 0.67,
    }
    resp = auth_client.post("/api/mileage/logs", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["miles"] == 50.0
    assert body["reimbursement_amount"] == 33.5


def test_api_mileage_summary(auth_client: TestClient, db: Session):
    _ensure_auth_user(db)
    payload = {
        "trip_date": "2026-06-01",
        "description": "Office supply run",
        "starting_odometer": 2000.0,
        "ending_odometer": 2030.0,
        "purpose": "business",
        "vehicle": "Honda Civic",
        "reimbursement_rate": 0.67,
    }
    resp = auth_client.post("/api/mileage/logs", json=payload)
    assert resp.status_code == 201
    resp = auth_client.get("/api/mileage/summary?year=2026")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["year"] == 2026
    assert body["total_miles"] == 30.0
    assert body["total_reimbursement"] == 20.1
