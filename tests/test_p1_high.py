"""
TaxFlow Pro v3.8 — P1 High Router Tests
========================================

Comprehensive tests for 11 routers:
1. Receipts (upload, list, get, delete, match with weighted confidence)
2. Budget (CRUD, vs-actual comparison)
3. OFX/Bank Connections (create, list, delete, Fernet encryption)
4. Exchange Rates (create, list, convert, bulk import)
5. Depreciation (all 5 methods, MACRS tables, validation)
6. Engagement (templates, create from template)
7. Batch Import (ZIP upload, status polling, list jobs)
8. Forecast (recurring template + historical fallback)
9. Settings (get/create, update, logo upload, thresholds)
10. Reclassify (single, bulk, categories)
11. Cross-cutting E2E (budget vs actual, receipt match flow)

All tests use FastAPI TestClient with fresh DB per test.
"""

import os
import sys
import json
import io
import zipfile
import tempfile
from decimal import Decimal
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash

test_engine = create_engine(
    "sqlite:///./test_p1_high.db",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    yield db
    db.rollback()
    db.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def auth_client(client):
    resp = client.post("/api/auth/register", json={
        "username": "p1user", "email": "p1@example.com", "password": "testpass123"
    })
    assert resp.status_code == 200
    uid = resp.json()["id"]

    resp = client.post("/api/auth/login", data={"username": "p1user", "password": "testpass123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, uid


@pytest.fixture(scope="function")
def seeded_client(auth_client):
    client, headers, user_id = auth_client
    resp = client.post("/api/clients/", headers=headers, json={
        "name": "P1 Test Business", "email": "p1@biz.com", "tax_id": "98-7654321"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=headers, json={
        "name": "P1 Checking", "institution": "Chase",
        "account_number_masked": "****9999", "type": "checking", "client_id": client_id
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]
    return {"client": client, "headers": headers, "user_id": user_id,
            "client_id": client_id, "account_id": account_id}


@pytest.fixture(scope="function")
def db_with_transactions(seeded_client):
    data = seeded_client
    db = TestSessionLocal()

    stmt = models.Statement(
        account_id=data["account_id"], tenant_id=data["client_id"],
        user_id=data["user_id"], filename="p1_stmt.pdf",
        period_start="2024-01-01", period_end="2024-12-31",
        opening_balance=Decimal("5000.00"), closing_balance=Decimal("3000.00"),
        variance=Decimal("-2000.00"), is_balanced=True,
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)

    txs = [
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-01-15",
            description="STARBUCKS #2847", amount=Decimal("-8.47"),
            tx_type="debit", category="Food & Dining", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-01-16",
            description="SHELL OIL 574421", amount=Decimal("-52.18"),
            tx_type="debit", category="Auto & Transport", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-02-01",
            description="OFFICE DEPOT #112", amount=Decimal("-127.50"),
            tx_type="debit", category="Office Expense", confirmed=False),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-02-15",
            description="AWS AMAZON WEB SERVICES", amount=Decimal("-450.00"),
            tx_type="debit", category="Software & SaaS", confirmed=True),
    ]
    for tx in txs:
        db.add(tx)
    db.commit()

    data["db"] = db
    data["statement_id"] = stmt.id
    data["transaction_ids"] = [tx.id for tx in txs]
    yield data
    db.close()


# =============================================================================
# RECEIPTS
# =============================================================================

class TestReceipts:
    """Receipt upload, listing, retrieval, deletion, and matching."""

    def _upload_receipt(self, client, headers, client_id, filename="test_receipt.png",
                        content=b"\x89PNG\r\n\x1a\n" + b"fake_png_data" * 100,
                        vendor="Starbucks", amount=8.47, receipt_date="2024-01-15"):
        return client.post(
            "/api/receipts/upload",
            headers=headers,
            data={"client_id": client_id, "vendor": vendor,
                  "amount": amount, "receipt_date": receipt_date},
            files={"file": (filename, io.BytesIO(content), "image/png")},
        )

    def test_upload_receipt(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._upload_receipt(c, h, cid)
        assert resp.status_code == 201, f"Upload failed: {resp.text}"
        data = resp.json()
        assert data["filename"] == "test_receipt.png"
        assert data["vendor"] == "Starbucks"
        assert data["amount"] == 8.47
        assert data["tenant_id"] == cid
        assert data["id"] is not None

    def test_upload_receipt_invalid_extension_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._upload_receipt(c, h, cid, filename="receipt.exe",
                                     content=b"MZ" + b"x" * 100)
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_list_receipts(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        self._upload_receipt(c, h, cid, filename="receipt_a.png")
        self._upload_receipt(c, h, cid, filename="receipt_b.png", vendor="Shell", amount=52.18)

        resp = c.get(f"/api/receipts?client_id={cid}", headers=h)
        assert resp.status_code == 200
        receipts = resp.json()
        assert len(receipts) == 2
        filenames = {r["filename"] for r in receipts}
        assert "receipt_a.png" in filenames

    def test_get_receipt_by_id(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        upload = self._upload_receipt(c, h, cid, vendor="Office Depot", amount=127.50)
        rid = upload.json()["id"]

        resp = c.get(f"/api/receipts/{rid}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == rid
        assert data["vendor"] == "Office Depot"
        assert data["amount"] == 127.50

    def test_get_nonexistent_receipt(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/receipts/99999", headers=h)
        assert resp.status_code == 404

    def test_delete_receipt(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        rid = self._upload_receipt(c, h, cid).json()["id"]

        resp = c.delete(f"/api/receipts/{rid}", headers=h)
        assert resp.status_code == 204

        resp = c.get(f"/api/receipts/{rid}", headers=h)
        assert resp.status_code == 404

    def test_delete_nonexistent_receipt(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.delete("/api/receipts/99999", headers=h)
        assert resp.status_code == 404

    def test_match_receipt_amount_weight(self, db_with_transactions):
        """Receipt with matching amount should get high confidence score."""
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        rid = self._upload_receipt(
            c, h, cid, filename="match_test.png",
            vendor="Starbucks", amount=8.47, receipt_date="2024-01-15",
        ).json()["id"]

        resp = c.post(f"/api/receipts/{rid}/match?client_id={cid}", headers=h)
        assert resp.status_code == 200
        matches = resp.json()
        assert len(matches) > 0
        # Highest confidence should be the Starbucks transaction (exact amount + date)
        top = matches[0]
        assert top["confidence"] > 50.0  # At least 50% from amount match
        assert top["factors"]["amount"] == 50.0  # Exact amount = full 50%

    def test_match_receipt_date_weight(self, db_with_transactions):
        """Receipt with matching date but different amount."""
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        rid = self._upload_receipt(
            c, h, cid, filename="date_match.png",
            vendor="Unknown", amount=999.99, receipt_date="2024-01-15",
        ).json()["id"]

        resp = c.post(f"/api/receipts/{rid}/match?client_id={cid}", headers=h)
        matches = resp.json()
        assert len(matches) > 0
        top = matches[0]
        # Should still match Jan 15 transaction, but lower confidence
        assert top["factors"]["date"] > 0

    def test_match_receipt_no_candidates(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        cid = seeded_client["client_id"]
        rid = self._upload_receipt(c, h, cid).json()["id"]
        resp = c.post(f"/api/receipts/{rid}/match?client_id={cid}", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_match_nonexistent_receipt(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        cid = seeded_client["client_id"]
        resp = c.post(f"/api/receipts/99999/match?client_id={cid}", headers=h)
        assert resp.status_code == 404


# =============================================================================
# BUDGET
# =============================================================================

class TestBudget:
    """Budget CRUD and budget-vs-actual comparison."""

    def _create_budget(self, client, headers, client_id, entries=None):
        if entries is None:
            entries = [
                {"category": "Food & Dining", "amount": 500.00},
                {"category": "Auto & Transport", "amount": 300.00},
                {"category": "Office Expense", "amount": 200.00},
            ]
        return client.post(
            f"/api/budgets/?client_id={client_id}",
            headers=headers,
            json={"name": "Test Budget", "period_start": "2024-01-01",
                  "period_end": "2024-12-31", "total_budget": 1000.00,
                  "is_active": True, "entries": entries},
        )

    def test_create_budget(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._create_budget(c, h, cid)
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Test Budget"
        assert data["tenant_id"] == cid
        assert len(data["entries"]) == 3

    def test_create_budget_no_entries(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._create_budget(c, h, cid, entries=[])
        assert resp.status_code == 201
        assert len(resp.json()["entries"]) == 0

    def test_list_budgets(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        self._create_budget(c, h, cid, name_override="Budget A")
        self._create_budget(c, h, cid, entries=[{"category": "Income", "amount": 5000}])

        resp = c.get(f"/api/budgets/?client_id={cid}", headers=h)
        assert resp.status_code == 200
        budgets = resp.json()
        assert len(budgets) >= 1

    def test_get_budget(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        budget_id = self._create_budget(c, h, cid).json()["id"]

        resp = c.get(f"/api/budgets/{budget_id}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == budget_id
        assert data["entries"][0]["category"] == "Food & Dining"
        assert "total_budget" in data

    def test_get_nonexistent_budget(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/budgets/99999", headers=h)
        assert resp.status_code == 404

    def test_update_budget(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        budget_id = self._create_budget(c, h, cid).json()["id"]

        resp = c.put(f"/api/budgets/{budget_id}", headers=h, json={
            "name": "Updated Budget", "period_start": "2024-01-01",
            "period_end": "2024-12-31", "total_budget": 2000.00,
            "is_active": True,
            "entries": [
                {"category": "Updated Cat", "amount": 2000.00},
            ],
        })
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Updated Budget"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["category"] == "Updated Cat"
        assert data["total_budget"] == 2000.00

    def test_delete_budget(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        budget_id = self._create_budget(c, h, cid).json()["id"]

        resp = c.delete(f"/api/budgets/{budget_id}", headers=h)
        assert resp.status_code == 204

        resp = c.get(f"/api/budgets/{budget_id}", headers=h)
        assert resp.status_code == 404

    def test_budget_vs_actual(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]

        # Create budget matching transaction categories
        budget_id = self._create_budget(c, h, cid, entries=[
            {"category": "Food & Dining", "amount": 500.00},
            {"category": "Auto & Transport", "amount": 300.00},
            {"category": "Office Expense", "amount": 1000.00},
        ]).json()["id"]

        resp = c.get(f"/api/budgets/{budget_id}/vs-actual", headers=h)
        assert resp.status_code == 200, f"vs-actual failed: {resp.text}"
        data = resp.json()
        assert data["budget_id"] == budget_id
        assert len(data["entries"]) >= 3  # Budget categories + any actual categories

        # Verify the food entry: budgeted 500, actual ~-8.47
        food = [e for e in data["entries"] if e["category"] == "food & dining"]
        assert len(food) == 1
        assert food[0]["budgeted"] == 500.00
        assert food[0]["actual"] < 0  # Actual is negative (debit)


# =============================================================================
# OFX / BANK CONNECTIONS
# =============================================================================

class TestOFX:
    """Bank connection CRUD and Fernet password encryption."""

    def test_create_connection(self, seeded_client, monkeypatch):
        monkeypatch.setenv("TAXFLOW_FERNET_KEY", "test_key_must_be_32_bytes_long!!")
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        aid = seeded_client["account_id"]

        resp = c.post("/api/bank-connections", headers=h, json={
            "account_id": aid, "institution_name": "Chase Bank",
            "connection_type": "ofx", "ofx_username": "testuser",
            "ofx_password": "secret123", "ofx_url": "https://ofx.chase.com",
            "ofx_org": "Chase", "ofx_fid": "10898",
            "routing_number": "021000021", "account_number": "123456789",
        })
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["institution_name"] == "Chase Bank"
        assert data["connection_type"] == "ofx"
        assert data["status"] == "active"
        assert "****" in data["ofx_password_masked"]
        assert data["account_number_masked"] == "*****6789"

    def test_list_connections(self, seeded_client, monkeypatch):
        monkeypatch.setenv("TAXFLOW_FERNET_KEY", "test_key_must_be_32_bytes_long!!")
        c, h, aid = seeded_client["client"], seeded_client["headers"], seeded_client["account_id"]

        c.post("/api/bank-connections", headers=h, json={
            "account_id": aid, "institution_name": "Bank A",
            "connection_type": "ofx", "ofx_username": "a", "ofx_password": "p",
        })
        c.post("/api/bank-connections", headers=h, json={
            "account_id": aid, "institution_name": "Bank B",
            "connection_type": "ofx", "ofx_username": "b", "ofx_password": "p",
        })

        resp = c.get("/api/bank-connections", headers=h)
        assert resp.status_code == 200
        conns = resp.json()
        assert len(conns) == 2
        names = {cn["institution_name"] for cn in conns}
        assert "Bank A" in names

    def test_delete_connection(self, seeded_client, monkeypatch):
        monkeypatch.setenv("TAXFLOW_FERNET_KEY", "test_key_must_be_32_bytes_long!!")
        c, h, aid = seeded_client["client"], seeded_client["headers"], seeded_client["account_id"]

        conn_id = c.post("/api/bank-connections", headers=h, json={
            "account_id": aid, "institution_name": "Temp Bank",
            "connection_type": "ofx", "ofx_username": "tmp", "ofx_password": "p",
        }).json()["id"]

        resp = c.delete(f"/api/bank-connections/{conn_id}", headers=h)
        assert resp.status_code == 204

        resp = c.get("/api/bank-connections", headers=h)
        assert not any(conn["id"] == conn_id for conn in resp.json())

    def test_create_connection_no_fernet_key_fails(self, seeded_client, monkeypatch):
        monkeypatch.delenv("TAXFLOW_FERNET_KEY", raising=False)
        c, h, aid = seeded_client["client"], seeded_client["headers"], seeded_client["account_id"]

        resp = c.post("/api/bank-connections", headers=h, json={
            "account_id": aid, "institution_name": "NoKey Bank",
            "connection_type": "ofx", "ofx_username": "u", "ofx_password": "p",
        })
        assert resp.status_code == 500
        assert "Fernet encryption key not configured" in resp.json()["detail"]

    def test_delete_nonexistent_connection(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.delete("/api/bank-connections/99999", headers=h)
        assert resp.status_code == 404


# =============================================================================
# EXCHANGE RATES
# =============================================================================

class TestExchangeRates:
    """Exchange rate CRUD, conversion, and bulk import."""

    def test_create_rate(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR",
            "rate": 0.92, "rate_date": "2024-01-15", "source": "test",
        })
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["from_currency"] == "USD"
        assert data["to_currency"] == "EUR"
        assert data["rate"] == 0.92
        assert data["tenant_id"] == cid

    def test_create_rate_uppercases_currency(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "gbp", "to_currency": "jpy",
            "rate": 185.50, "rate_date": "2024-01-15",
        })
        assert resp.json()["from_currency"] == "GBP"
        assert resp.json()["to_currency"] == "JPY"

    def test_create_rate_zero_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR",
            "rate": 0, "rate_date": "2024-01-15",
        })
        assert resp.status_code == 400
        assert "Rate must be positive" in resp.json()["detail"]

    def test_create_rate_negative_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR",
            "rate": -1.5, "rate_date": "2024-01-15",
        })
        assert resp.status_code == 400

    def test_update_existing_rate(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "CAD",
            "rate": 1.35, "rate_date": "2024-01-15",
        })
        resp = c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "CAD",
            "rate": 1.38, "rate_date": "2024-01-15",
        })
        assert resp.status_code == 201  # Updates existing
        assert resp.json()["rate"] == 1.38

    def test_list_rates(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        for pair in [("USD", "EUR", 0.92), ("USD", "GBP", 0.79), ("EUR", "JPY", 160)]:
            c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
                "from_currency": pair[0], "to_currency": pair[1],
                "rate": pair[2], "rate_date": "2024-01-15",
            })

        resp = c.get(f"/api/exchange-rates/?client_id={cid}", headers=h)
        assert resp.status_code == 200
        rates = resp.json()
        assert len(rates) == 3

    def test_list_rates_filtered_by_currency(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR", "rate": 0.92, "rate_date": "2024-01-15",
        })
        c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "GBP", "rate": 0.79, "rate_date": "2024-01-15",
        })

        resp = c.get(f"/api/exchange-rates/?client_id={cid}&from_currency=USD&to_currency=EUR", headers=h)
        assert resp.status_code == 200
        rates = resp.json()
        assert len(rates) == 1
        assert rates[0]["to_currency"] == "EUR"

    def test_convert_currency(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR",
            "rate": 0.92, "rate_date": "2024-01-15",
        })

        resp = c.get(f"/api/exchange-rates/convert?client_id={cid}&from_currency=USD&to_currency=EUR&amount=100", headers=h)
        assert resp.status_code == 200, f"Convert failed: {resp.text}"
        data = resp.json()
        assert data["from_currency"] == "USD"
        assert data["to_currency"] == "EUR"
        assert data["amount"] == 100.0
        assert abs(data["converted_amount"] - 92.0) < 0.01
        assert data["rate"] == 0.92

    def test_convert_currency_inverse_rate(self, seeded_client):
        """Convert EUR->USD using only USD->EUR rate stored."""
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR",
            "rate": 0.92, "rate_date": "2024-01-15",
        })

        resp = c.get(f"/api/exchange-rates/convert?client_id={cid}&from_currency=EUR&to_currency=USD&amount=92", headers=h)
        assert resp.status_code == 200
        # Should use inverse: 92 / 0.92 = ~100
        assert abs(data["converted_amount"] - 100.0) < 1.0

    def test_convert_currency_not_found(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.get(f"/api/exchange-rates/convert?client_id={cid}&from_currency=XXX&to_currency=YYY&amount=100", headers=h)
        assert resp.status_code == 404

    def test_bulk_import_rates(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/exchange-rates/import?client_id={cid}", headers=h, json={
            "rates": [
                {"from_currency": "USD", "to_currency": "MXN", "rate": 17.15, "rate_date": "2024-01-15"},
                {"from_currency": "USD", "to_currency": "CNY", "rate": 7.19, "rate_date": "2024-01-15"},
                {"from_currency": "EUR", "to_currency": "CHF", "rate": 0.94, "rate_date": "2024-01-15"},
            ]
        })
        assert resp.status_code == 200, f"Bulk import failed: {resp.text}"
        data = resp.json()
        assert data["created"] == 3
        assert data["errors"] is None or len(data["errors"]) == 0

    def test_bulk_import_with_invalid_rate(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/exchange-rates/import?client_id={cid}", headers=h, json={
            "rates": [
                {"from_currency": "USD", "to_currency": "MXN", "rate": 17.15, "rate_date": "2024-01-15"},
                {"from_currency": "BAD", "to_currency": "PAIR", "rate": -5.0, "rate_date": "2024-01-15"},
            ]
        })
        assert resp.status_code == 200
        assert resp.json()["errors"] is not None
        assert len(resp.json()["errors"]) == 1


# =============================================================================
# DEPRECIATION
# =============================================================================

class TestDepreciation:
    """Depreciation calculation for all 5 methods and MACRS tables."""

    def test_list_methods(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/depreciation/methods", headers=h)
        assert resp.status_code == 200
        methods = resp.json()
        assert len(methods) == 5
        codes = {m["code"] for m in methods}
        assert "macrs_hy" in codes
        assert "straight_line" in codes
        assert "section_179" in codes
        assert "bonus_60" in codes
        assert "macrs_mq" in codes

    def test_macrs_tables(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/depreciation/macrs-tables", headers=h)
        assert resp.status_code == 200
        tables = resp.json()
        assert "5" in tables
        assert tables["5"]["name"] == "5-Year Property"
        assert len(tables["5"]["yearly_percentages"]) == 6  # HY has N+1 years
        # Verify percentages sum to ~100%
        total_5yr = sum(tables["5"]["yearly_percentages"])
        assert abs(total_5yr - 100.0) < 0.1

    def test_calculate_macrs_half_year_5year(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Computer Equipment", "asset_class": "5-Year",
            "cost_basis": 10000.00, "placed_in_service_date": "2024-06-15",
            "recovery_period": 5, "method": "macrs_hy",
        })
        assert resp.status_code == 200, f"MACRS calc failed: {resp.text}"
        data = resp.json()
        assert data["asset_name"] == "Computer Equipment"
        assert data["method"] == "macrs_hy"
        assert data["cost_basis"] == 10000.00
        assert len(data["schedule"]) == 6  # 5-year + half-year = 6 periods
        # First year: 20% of depreciable basis
        first_year = data["schedule"][0]
        assert first_year["deduction"] > 0
        assert first_year["year"] == 2024

    def test_calculate_straight_line(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Building Improvements", "asset_class": "SL",
            "cost_basis": 50000.00, "placed_in_service_date": "2024-01-01",
            "recovery_period": 10, "method": "straight_line",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "straight_line"
        assert len(data["schedule"]) == 10
        # SL: each year should have same deduction
        deductions = [y["deduction"] for y in data["schedule"]]
        assert all(d == deductions[0] for d in deductions)

    def test_calculate_section_179(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Delivery Truck", "asset_class": "Vehicle",
            "cost_basis": 50000.00, "placed_in_service_date": "2024-01-01",
            "recovery_period": 5, "method": "section_179",
            "section_179_expense": 25000.00,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["section_179_expense"] == 25000.00
        assert data["total_deduction"] >= 25000.00

    def test_calculate_bonus_60(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Manufacturing Equipment", "asset_class": "7-Year",
            "cost_basis": 200000.00, "placed_in_service_date": "2024-01-01",
            "recovery_period": 7, "method": "bonus_60",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["method"] == "bonus_60"
        assert data["bonus_depreciation"] == 120000.00  # 60% of 200k

    def test_calculate_zero_cost_basis_fails(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Free Item", "asset_class": "Test",
            "cost_basis": 0, "placed_in_service_date": "2024-01-01",
            "recovery_period": 5, "method": "macrs_hy",
        })
        assert resp.status_code == 400
        assert "Cost basis must be positive" in resp.json()["detail"]

    def test_calculate_negative_recovery_period_fails(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Bad", "asset_class": "Test",
            "cost_basis": 1000, "placed_in_service_date": "2024-01-01",
            "recovery_period": -1, "method": "macrs_hy",
        })
        assert resp.status_code == 400
        assert "Recovery period must be positive" in resp.json()["detail"]

    def test_calculate_business_use_percentage(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Mixed-Use Vehicle", "asset_class": "5-Year",
            "cost_basis": 30000.00, "placed_in_service_date": "2024-01-01",
            "recovery_period": 5, "method": "macrs_hy",
            "business_use_pct": 80.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["business_use_pct"] == 80.0
        # Deductions should be ~80% of what they'd be at 100%

    def test_calculate_invalid_business_use_fails(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Bad", "asset_class": "Test",
            "cost_basis": 1000, "placed_in_service_date": "2024-01-01",
            "recovery_period": 5, "method": "macrs_hy",
            "business_use_pct": 120.0,
        })
        assert resp.status_code == 400
        assert "Business use percentage" in resp.json()["detail"]

    def test_calculate_27_5_year_residential(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/depreciation/calculate", headers=h, json={
            "asset_name": "Rental House", "asset_class": "Residential",
            "cost_basis": 300000.00, "placed_in_service_date": "2024-01-01",
            "recovery_period": 27.5, "method": "macrs_hy",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["schedule"]) >= 27


# =============================================================================
# ENGAGEMENT
# =============================================================================

class TestEngagement:
    """Engagement template listing, detail, and creation from template."""

    def test_list_templates(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/engagements/templates", headers=h)
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) == 6
        types = {t["template_type"] for t in templates}
        assert "tax_return_individual" in types
        assert "bookkeeping_monthly" in types
        assert "consulting" in types

    def test_get_template_detail(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/engagements/templates/tax_return_individual", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_type"] == "tax_return_individual"
        assert data["name"] == "Individual Tax Return Preparation"
        assert "body" in data
        assert len(data["checklist_items"]) == 10
        assert "W-2 Forms" in data["checklist_items"]
        assert data["default_fee"] == 850.00

    def test_get_nonexistent_template(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/engagements/templates/nonexistent", headers=h)
        assert resp.status_code == 404

    def test_create_engagement_from_template(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post("/api/engagements/from-template", headers=h, json={
            "template_type": "tax_return_individual",
            "client_id": cid,
            "engagement_name": "John Doe 2024 Tax Return",
            "due_date": "2024-04-15",
            "custom_fee": 950.00,
            "notes": "Includes foreign income reporting",
        })
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "John Doe 2024 Tax Return"
        assert data["tenant_id"] == cid
        assert data["status"] == "draft"
        assert "body" in data["description"]

    def test_create_engagement_uses_default_name(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post("/api/engagements/from-template", headers=h, json={
            "template_type": "bookkeeping_monthly", "client_id": cid,
        })
        assert resp.status_code == 201
        assert "Monthly Bookkeeping" in resp.json()["name"]

    def test_create_engagement_invalid_template(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post("/api/engagements/from-template", headers=h, json={
            "template_type": "nonexistent", "client_id": cid,
        })
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_create_engagement_wrong_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/engagements/from-template", headers=h, json={
            "template_type": "tax_return_individual", "client_id": 99999,
        })
        assert resp.status_code == 404


# =============================================================================
# BATCH IMPORT
# =============================================================================

class TestBatchImport:
    """ZIP upload, job creation, status polling, and listing."""

    def _create_zip(self, filename="test.csv", content="date,description,amount,tx_type\n2024-01-15,Test TX,100.00,debit\n"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename, content)
        buf.seek(0)
        return buf.read()

    def test_upload_zip_creates_job(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        zip_data = self._create_zip()

        resp = c.post(
            f"/api/batch-import/?client_id={cid}",
            headers=h,
            files={"file": ("test_import.zip", io.BytesIO(zip_data), "application/zip")},
        )
        assert resp.status_code == 202, f"Upload failed: {resp.text}"
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "check_status_at" in data

    def test_upload_non_zip_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(
            f"/api/batch-import/?client_id={cid}",
            headers=h,
            files={"file": ("test.txt", io.BytesIO(b"not a zip"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "Only ZIP files" in resp.json()["detail"]

    def test_get_job_status(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        zip_data = self._create_zip()
        job = c.post(
            f"/api/batch-import/?client_id={cid}",
            headers=h,
            files={"file": ("status_test.zip", io.BytesIO(zip_data), "application/zip")},
        ).json()
        job_id = job["job_id"]

        resp = c.get(f"/api/batch-import/{job_id}/status", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "processing", "completed", "completed_with_errors")

    def test_get_nonexistent_job(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/batch-import/99999/status", headers=h)
        assert resp.status_code == 404

    def test_list_jobs(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        zip_data = self._create_zip()

        for name in ["job_a.zip", "job_b.zip"]:
            c.post(
                f"/api/batch-import/?client_id={cid}",
                headers=h,
                files={"file": (name, io.BytesIO(zip_data), "application/zip")},
            )

        resp = c.get(f"/api/batch-import/jobs?client_id={cid}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["jobs"]) >= 2

    def test_upload_empty_zip(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            pass  # Empty zip
        buf.seek(0)

        resp = c.post(
            f"/api/batch-import/?client_id={cid}",
            headers=h,
            files={"file": ("empty.zip", io.BytesIO(buf.read()), "application/zip")},
        )
        assert resp.status_code == 202  # Accepted, will fail processing


# =============================================================================
# FORECAST
# =============================================================================

class TestForecast:
    """Cash flow forecasting via recurring templates and historical fallback."""

    def test_forecast_historical_fallback(self, db_with_transactions):
        """When no recurring templates exist, forecast falls back to historical average."""
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]

        resp = c.get(f"/api/forecast?client_id={cid}&months_ahead=6", headers=h)
        assert resp.status_code == 200, f"Forecast failed: {resp.text}"
        data = resp.json()
        assert data["client_id"] == cid
        assert data["months_ahead"] == 6
        assert data["methodology"] == "historical_average_6m"
        assert len(data["entries"]) == 6
        # Each entry should have the fields
        entry = data["entries"][0]
        assert "month" in entry
        assert "predicted_income" in entry
        assert "predicted_expenses" in entry
        assert "net" in entry

    def test_forecast_from_recurring_templates(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        db = TestSessionLocal()

        # Create recurring templates
        templates = [
            models.RecurringTemplate(
                tenant_id=cid, user_id=seeded_client["user_id"],
                name="Monthly Rent", description="Office rent",
                amount=1500.00, tx_type="debit", category="Rent",
                frequency="monthly", start_date="2024-01-01",
            ),
            models.RecurringTemplate(
                tenant_id=cid, user_id=seeded_client["user_id"],
                name="Client Revenue", description="Monthly retainer",
                amount=5000.00, tx_type="credit", category="Income",
                frequency="monthly", start_date="2024-01-01",
            ),
        ]
        for t in templates:
            db.add(t)
        db.commit()
        db.close()

        resp = c.get(f"/api/forecast?client_id={cid}&months_ahead=6", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["methodology"] == "recurring_templates"
        assert len(data["entries"]) == 6

        # Net should be positive: 5000 income - 1500 rent = 3500
        first = data["entries"][0]
        assert first["predicted_income"] == 5000.00
        assert first["predicted_expenses"] == 1500.00
        assert first["net"] == 3500.00

    def test_forecast_quarterly_template(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        db = TestSessionLocal()
        db.add(models.RecurringTemplate(
            tenant_id=cid, user_id=seeded_client["user_id"],
            name="Quarterly Tax Payment", amount=3000.00,
            tx_type="debit", category="Taxes",
            frequency="quarterly", start_date="2024-01-01",
        ))
        db.commit()
        db.close()

        resp = c.get(f"/api/forecast?client_id={cid}&months_ahead=6", headers=h)
        data = resp.json()
        assert data["methodology"] == "recurring_templates"
        # Quarterly should appear in months 1, 4 (every 3rd)
        months_with_tax = [e for e in data["entries"] if e["predicted_expenses"] > 0]
        assert len(months_with_tax) <= 2  # At most 2 quarterly occurrences in 6 months

    def test_forecast_months_ahead_validation(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.get(f"/api/forecast?client_id={cid}&months_ahead=0", headers=h)
        assert resp.status_code == 422  # FastAPI validates ge=1

    def test_forecast_nonexistent_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/forecast?client_id=99999&months_ahead=6", headers=h)
        assert resp.status_code == 404

    def test_forecast_totals(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]

        resp = c.get(f"/api/forecast?client_id={cid}&months_ahead=3", headers=h)
        data = resp.json()
        assert "total_predicted_income" in data
        assert "total_predicted_expenses" in data
        assert "total_net" in data
        assert abs(data["total_net"] - (data["total_predicted_income"] - data["total_predicted_expenses"])) < 0.01


# =============================================================================
# SETTINGS
# =============================================================================

class TestSettings:
    """Firm settings CRUD, logo upload, recurring thresholds."""

    def test_get_settings_creates_defaults(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.get(f"/api/settings?client_id={cid}", headers=h)
        assert resp.status_code == 200, f"Get settings failed: {resp.text}"
        data = resp.json()
        assert data["tenant_id"] == cid
        assert data["timezone"] == "America/New_York"
        assert data["date_format"] == "%m/%d/%Y"

    def test_update_settings(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.put(f"/api/settings?client_id={cid}", headers=h, json={
            "firm_name": "Smith & Associates CPA",
            "firm_address": "123 Main St, Suite 100",
            "firm_phone": "(555) 123-4567",
            "firm_email": "info@smithcpa.com",
            "firm_ein": "12-3456789",
            "timezone": "America/Chicago",
        })
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data["firm_name"] == "Smith & Associates CPA"
        assert data["firm_phone"] == "(555) 123-4567"
        assert data["timezone"] == "America/Chicago"

    def test_get_thresholds_default(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.get(f"/api/settings/recurring-thresholds?client_id={cid}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["high_confidence"] == 0.85
        assert data["medium_confidence"] == 0.60
        assert data["auto_confirm"] == 0.95

    def test_update_thresholds(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.put(f"/api/settings/recurring-thresholds?client_id={cid}", headers=h, json={
            "high_confidence": 0.90, "medium_confidence": 0.70, "auto_confirm": 0.98,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["high_confidence"] == 0.90
        assert data["medium_confidence"] == 0.70
        assert data["auto_confirm"] == 0.98

    def test_update_thresholds_validation(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        # High < medium should fail
        resp = c.put(f"/api/settings/recurring-thresholds?client_id={cid}", headers=h, json={
            "high_confidence": 0.50, "medium_confidence": 0.70, "auto_confirm": 0.95,
        })
        assert resp.status_code == 400
        assert "high_confidence must be >= medium_confidence" in resp.json()["detail"]

    def test_update_thresholds_out_of_range(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.put(f"/api/settings/recurring-thresholds?client_id={cid}", headers=h, json={
            "high_confidence": 1.5, "medium_confidence": 0.70, "auto_confirm": 0.95,
        })
        assert resp.status_code == 400

    def test_upload_logo(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        png_header = b"\x89PNG\r\n\x1a\n" + b"logo_data" * 50
        resp = c.post(
            f"/api/settings/logo/upload?client_id={cid}",
            headers=h,
            files={"file": ("firm_logo.png", io.BytesIO(png_header), "image/png")},
        )
        assert resp.status_code == 200, f"Logo upload failed: {resp.text}"
        data = resp.json()
        assert "logo_path" in data
        assert "firm_logo.png" in data["filename"] or "logo_" in data["filename"]

    def test_upload_logo_invalid_extension(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(
            f"/api/settings/logo/upload?client_id={cid}",
            headers=h,
            files={"file": ("logo.exe", io.BytesIO(b"bad"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]


# =============================================================================
# RECLASSIFY
# =============================================================================

class TestReclassify:
    """Transaction reclassification (single and bulk) and category listing."""

    def test_list_categories(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/categories", headers=h)
        assert resp.status_code == 200
        cats = resp.json()
        assert len(cats) == 41  # All tax categories
        codes = {c["code"] for c in cats}
        assert "advertising" in codes
        assert "meals" in codes
        assert "wages" in codes

    def test_list_categories_filtered_by_schedule(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/categories?schedule=C", headers=h)
        assert resp.status_code == 200
        cats = resp.json()
        assert all(c["schedule"] == "C" for c in cats)
        assert len(cats) > 20

    def test_reclassify_transaction(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]

        resp = c.post(f"/api/transactions/{tx_id}/reclassify", headers=h, json={
            "new_category": "advertising", "reason": "Marketing expense",
        })
        assert resp.status_code == 200, f"Reclassify failed: {resp.text}"
        data = resp.json()
        assert data["transaction_id"] == tx_id
        assert data["old_category"] == "Food & Dining"
        assert data["new_category"] == "advertising"
        assert data["success"] is True

    def test_reclassify_nonexistent_transaction(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/transactions/99999/reclassify", headers=h, json={
            "new_category": "advertising",
        })
        assert resp.status_code == 404

    def test_bulk_reclassify(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_ids = db_with_transactions["transaction_ids"][:3]

        resp = c.post("/api/transactions/bulk-reclassify", headers=h, json={
            "transaction_ids": tx_ids,
            "new_category": "supplies",
            "reason": "Year-end reclassification",
        })
        assert resp.status_code == 200, f"Bulk reclassify failed: {resp.text}"
        data = resp.json()
        assert data["total_success"] == 3
        assert data["total_failed"] == 0
        assert len(data["results"]) == 3
        for r in data["results"]:
            assert r["success"] is True
            assert r["new_category"] == "supplies"

    def test_bulk_reclassify_empty_list_fails(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/transactions/bulk-reclassify", headers=h, json={
            "transaction_ids": [], "new_category": "supplies",
        })
        assert resp.status_code == 400
        assert "No transaction IDs" in resp.json()["detail"]

    def test_bulk_reclassify_with_invalid_ids(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_ids = [99998, 99999]

        resp = c.post("/api/transactions/bulk-reclassify", headers=h, json={
            "transaction_ids": tx_ids,
            "new_category": "supplies",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_success"] == 0
        assert data["total_failed"] == 2


# =============================================================================
# CROSS-CUTTING E2E
# =============================================================================

class TestCrossCuttingP1:
    """End-to-end workflows spanning multiple routers."""

    def test_budget_vs_actual_with_reclassify(self, db_with_transactions):
        """
        1. Create budget with categories
        2. Reclassify a transaction to match budget category
        3. Verify budget-vs-actual reflects the reclassification
        """
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        tx_id = db_with_transactions["transaction_ids"][0]  # Food & Dining

        # Create budget
        budget_id = c.post(f"/api/budgets/?client_id={cid}", headers=h, json={
            "name": "Cross-Cutting Budget", "period_start": "2024-01-01",
            "period_end": "2024-12-31", "total_budget": 1000.00, "is_active": True,
            "entries": [{"category": "supplies", "amount": 1000.00}],
        }).json()["id"]

        # Reclassify transaction to match budget category
        c.post(f"/api/transactions/{tx_id}/reclassify", headers=h, json={
            "new_category": "supplies", "reason": "Budget alignment",
        })

        # Check budget vs actual
        resp = c.get(f"/api/budgets/{budget_id}/vs-actual", headers=h)
        data = resp.json()
        supplies = [e for e in data["entries"] if e["category"] == "supplies"]
        assert len(supplies) == 1
        assert supplies[0]["budgeted"] == 1000.00
        assert supplies[0]["actual"] < 0  # The reclassified transaction

    def test_receipt_match_to_reclassified_transaction(self, db_with_transactions):
        """
        1. Reclassify a transaction
        2. Upload receipt with matching amount/date
        3. Verify receipt match finds the reclassified transaction
        """
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        tx_id = db_with_transactions["transaction_ids"][0]

        # Reclassify to a new category
        c.post(f"/api/transactions/{tx_id}/reclassify", headers=h, json={
            "new_category": "meals", "reason": "50% deductible",
        })

        # Upload receipt matching the transaction
        png = b"\x89PNG\r\n\x1a\n" + b"receipt" * 100
        rid = c.post(
            "/api/receipts/upload",
            headers=h,
            data={"client_id": cid, "vendor": "Starbucks", "amount": 8.47, "receipt_date": "2024-01-15"},
            files={"file": ("sbux.png", io.BytesIO(png), "image/png")},
        ).json()["id"]

        # Match should find the reclassified transaction
        resp = c.post(f"/api/receipts/{rid}/match?client_id={cid}", headers=h)
        matches = resp.json()
        assert len(matches) > 0
        top = matches[0]
        assert top["confidence"] > 50.0

    def test_full_client_lifecycle(self, seeded_client):
        """
        Create client -> account -> budget -> exchange rate -> settings
        -> verify all are linked correctly.
        """
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]

        # Budget
        budget = c.post(f"/api/budgets/?client_id={cid}", headers=h, json={
            "name": "Annual Budget", "period_start": "2024-01-01",
            "period_end": "2024-12-31", "total_budget": 50000.00, "is_active": True,
            "entries": [{"category": "Wages", "amount": 30000.00}],
        }).json()
        assert budget["tenant_id"] == cid

        # Exchange rate
        rate = c.post(f"/api/exchange-rates/?client_id={cid}", headers=h, json={
            "from_currency": "USD", "to_currency": "EUR",
            "rate": 0.92, "rate_date": "2024-01-15",
        }).json()
        assert rate["tenant_id"] == cid

        # Settings
        settings = c.get(f"/api/settings?client_id={cid}", headers=h).json()
        assert settings["tenant_id"] == cid

        # All linked to same client
        assert budget["tenant_id"] == settings["tenant_id"] == rate["tenant_id"]
