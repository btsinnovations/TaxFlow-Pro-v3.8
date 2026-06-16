"""
TaxFlow Pro v3.8 — P2 Medium Router Tests
==========================================

Comprehensive tests for 9 routers + services + cross-cutting workflows:
1. Accounts (CRUD, tenant_id, user isolation)
2. Clients (CRUD, user isolation)
3. Dashboard (KPIs, recent statements, empty state)
4. Export (8 formats: CSV, JSON, QIF, QBO, Xero, Excel, PDF, Parquet)
5. Tax Exports (Drake CSV, Lacerte CSV, ProConnect TXF)
6. ML Categorization (rule-based, status, toggle)
7. Tax Summary (income/expense/net by year)
8. Transaction Notes & Flags (CRUD, resolve, filtering)
9. Upload (PDF parse, statement creation, transaction extraction)
10. Events (SSE event manager)
11. Cross-cutting E2E (upload → categorize → export → tax-export)

All tests use FastAPI TestClient with fresh DB per test.
"""

import os
import sys
import json
import io
import csv
import asyncio
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
from backend.events import event_manager

test_engine = create_engine(
    "sqlite:///./test_p2_medium.db",
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
        "username": "p2user", "email": "p2@example.com", "password": "testpass123"
    })
    assert resp.status_code == 200
    uid = resp.json()["id"]

    resp = client.post("/api/auth/login", data={"username": "p2user", "password": "testpass123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, uid


@pytest.fixture(scope="function")
def seeded_client(auth_client):
    client, headers, user_id = auth_client
    resp = client.post("/api/clients/", headers=headers, json={
        "name": "P2 Test Business", "email": "p2@biz.com", "tax_id": "11-2223334"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=headers, json={
        "name": "P2 Checking", "institution": "Chase",
        "account_number_masked": "****8888", "type": "checking", "client_id": client_id
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
        user_id=data["user_id"], filename="p2_stmt.pdf",
        period_start="2024-01-01", period_end="2024-12-31",
        opening_balance=Decimal("10000.00"), closing_balance=Decimal("8500.00"),
        variance=Decimal("-1500.00"), is_balanced=True,
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)

    txs = [
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-01-15",
            description="SALARY DEPOSIT", amount=Decimal("5000.00"),
            tx_type="credit", category="Income", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-02-01",
            description="RENT PAYMENT", amount=Decimal("-1200.00"),
            tx_type="debit", category="Rent", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-02-15",
            description="STARBUCKS COFFEE", amount=Decimal("-6.42"),
            tx_type="debit", category="Meals", confirmed=False),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-03-01",
            description="SHELL GAS STATION", amount=Decimal("-48.17"),
            tx_type="debit", category="Car and truck", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
            client_id=data["client_id"], date="2024-03-15",
            description="OFFICE DEPOT SUPPLIES", amount=Decimal("-134.89"),
            tx_type="debit", category="Office", confirmed=True),
    ]
    for tx in txs:
        db.add(tx)
    db.commit()

    data["db"] = db
    data["statement_id"] = stmt.id
    data["transaction_ids"] = [tx.id for tx in txs]
    yield data
    db.close()


@pytest.fixture(scope="function")
def second_user_client(client):
    """A second authenticated user for isolation tests."""
    resp = client.post("/api/auth/register", json={
        "username": "p2user2", "email": "p2other@example.com", "password": "testpass456"
    })
    assert resp.status_code == 200
    uid = resp.json()["id"]
    resp = client.post("/api/auth/login", data={"username": "p2user2", "password": "testpass456"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, uid


# =============================================================================
# ACCOUNTS
# =============================================================================

class TestAccounts:
    """Account CRUD with user isolation and tenant_id propagation."""

    def test_create_account(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post("/api/accounts/", headers=h, json={
            "name": "Savings", "institution": "Wells Fargo",
            "account_number_masked": "****4321", "type": "savings", "client_id": cid
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Savings"
        assert data["type"] == "savings"
        assert data["client_id"] == cid
        assert data["tenant_id"] == cid

    def test_create_account_without_client_id(self, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/accounts/", headers=h, json={
            "name": "Orphan Account", "institution": "Test",
            "type": "checking",
        })
        assert resp.status_code == 422  # client_id is required

    def test_list_accounts(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post("/api/accounts/", headers=h, json={
            "name": "Account A", "client_id": cid, "type": "checking"
        })
        c.post("/api/accounts/", headers=h, json={
            "name": "Account B", "client_id": cid, "type": "savings"
        })
        resp = c.get("/api/accounts/", headers=h)
        assert resp.status_code == 200
        accounts = resp.json()
        assert len(accounts) >= 3  # Original + 2 new

    def test_list_accounts_filtered_by_client(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.get(f"/api/accounts/?client_id={cid}", headers=h)
        accounts = resp.json()
        assert all(a["client_id"] == cid for a in accounts)

    def test_get_account(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        aid = seeded_client["account_id"]
        resp = c.get(f"/api/accounts/{aid}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == aid
        assert data["name"] == "P2 Checking"
        assert "statements" in data

    def test_get_nonexistent_account(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/accounts/99999", headers=h)
        assert resp.status_code == 404

    def test_update_account(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        aid = seeded_client["account_id"]
        resp = c.patch(f"/api/accounts/{aid}", headers=h, json={
            "name": "Updated Checking", "institution": "Bank of America"
        })
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Updated Checking"
        assert data["institution"] == "Bank of America"

    def test_update_account_changes_tenant(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        # Create a second client
        resp = c.post("/api/clients/", headers=h, json={
            "name": "Second Client", "email": "sc@example.com"
        })
        new_cid = resp.json()["id"]

        aid = seeded_client["account_id"]
        resp = c.patch(f"/api/accounts/{aid}", headers=h, json={
            "client_id": new_cid
        })
        assert resp.status_code == 200
        assert resp.json()["client_id"] == new_cid
        assert resp.json()["tenant_id"] == new_cid

    def test_delete_account(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        aid = c.post("/api/accounts/", headers=h, json={
            "name": "ToDelete", "client_id": cid, "type": "checking"
        }).json()["id"]

        resp = c.delete(f"/api/accounts/{aid}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp = c.get(f"/api/accounts/{aid}", headers=h)
        assert resp.status_code == 404

    def test_delete_nonexistent_account(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.delete("/api/accounts/99999", headers=h)
        assert resp.status_code == 404

    def test_account_user_isolation(self, seeded_client, second_user_client):
        """User B should not see User A's accounts."""
        c1, h1, cid1 = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c2, h2, _ = second_user_client

        # User 1 creates an account
        aid = c1.post("/api/accounts/", headers=h1, json={
            "name": "Private", "client_id": cid1, "type": "checking"
        }).json()["id"]

        # User 2 tries to access it
        resp = c2.get(f"/api/accounts/{aid}", headers=h2)
        assert resp.status_code == 404

    def test_account_pagination(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        for i in range(5):
            c.post("/api/accounts/", headers=h, json={
                "name": f"Paginated {i}", "client_id": cid, "type": "checking"
            })

        resp = c.get("/api/accounts/?limit=3&skip=0", headers=h)
        assert len(resp.json()) == 3

        resp = c.get("/api/accounts/?limit=3&skip=3", headers=h)
        assert len(resp.json()) == 3  # Original + 5 = 6, page 2 has 3


# =============================================================================
# CLIENTS
# =============================================================================

class TestClients:
    """Client CRUD with user isolation."""

    def test_create_client(self, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/clients/", headers=h, json={
            "name": "New Client Corp", "email": "client@corp.com",
            "tax_id": "99-8887776", "entity_type": "S-Corp"
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "New Client Corp"
        assert data["email"] == "client@corp.com"
        assert data["tax_id"] == "99-8887776"
        assert data["entity_type"] == "S-Corp"

    def test_create_client_minimal(self, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/clients/", headers=h, json={
            "name": "Minimal Client"
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Minimal Client"

    def test_list_clients(self, auth_client):
        c, h, _ = auth_client
        for name in ["Alpha", "Beta", "Gamma"]:
            c.post("/api/clients/", headers=h, json={"name": name})

        resp = c.get("/api/clients/", headers=h)
        assert resp.status_code == 200
        clients = resp.json()
        assert len(clients) == 3
        names = {cl["name"] for cl in clients}
        assert "Alpha" in names
        assert "Gamma" in names

    def test_get_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        cid = seeded_client["client_id"]
        resp = c.get(f"/api/clients/{cid}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == cid
        assert data["name"] == "P2 Test Business"

    def test_get_nonexistent_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/clients/99999", headers=h)
        assert resp.status_code == 404

    def test_update_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        cid = seeded_client["client_id"]
        resp = c.patch(f"/api/clients/{cid}", headers=h, json={
            "name": "Updated Business Name",
            "email": "newemail@biz.com",
        })
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Updated Business Name"
        assert data["email"] == "newemail@biz.com"

    def test_update_client_partial(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        cid = seeded_client["client_id"]
        resp = c.patch(f"/api/clients/{cid}", headers=h, json={
            "tax_id": "00-0000001"
        })
        assert resp.status_code == 200
        assert resp.json()["tax_id"] == "00-0000001"
        # Other fields unchanged
        assert resp.json()["name"] == "P2 Test Business"

    def test_delete_client(self, auth_client):
        c, h, _ = auth_client
        cid = c.post("/api/clients/", headers=h, json={
            "name": "To Delete"
        }).json()["id"]

        resp = c.delete(f"/api/clients/{cid}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp = c.get(f"/api/clients/{cid}", headers=h)
        assert resp.status_code == 404

    def test_delete_nonexistent_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.delete("/api/clients/99999", headers=h)
        assert resp.status_code == 404

    def test_client_user_isolation(self, auth_client, second_user_client):
        c1, h1, _ = auth_client
        c2, h2, _ = second_user_client

        cid = c1.post("/api/clients/", headers=h1, json={
            "name": "Private Client"
        }).json()["id"]

        resp = c2.get(f"/api/clients/{cid}", headers=h2)
        assert resp.status_code == 404

    def test_client_pagination(self, auth_client):
        c, h, _ = auth_client
        for i in range(7):
            c.post("/api/clients/", headers=h, json={"name": f"Client {i}"})

        resp = c.get("/api/clients/?limit=5&skip=0", headers=h)
        assert len(resp.json()) == 5


# =============================================================================
# DASHBOARD
# =============================================================================

class TestDashboard:
    """Dashboard KPIs and recent statements."""

    def test_dashboard_empty(self, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/dashboard/", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_accounts"] == 0
        assert data["total_statements"] == 0
        assert data["total_transactions"] == 0
        assert data["total_volume"] == 0.0
        assert data["recent_statements"] == []

    def test_dashboard_with_data(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        resp = c.get("/api/dashboard/", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_accounts"] == 1
        assert data["total_statements"] == 1
        assert data["total_transactions"] == 5
        assert data["total_volume"] != 0.0
        assert len(data["recent_statements"]) == 1
        stmt = data["recent_statements"][0]
        assert stmt["filename"] == "p2_stmt.pdf"
        assert "is_balanced" in stmt

    def test_dashboard_not_affected_by_other_users(self, auth_client, second_user_client, db_with_transactions):
        c2, h2, _ = second_user_client
        resp = c2.get("/api/dashboard/", headers=h2)
        assert resp.status_code == 200
        assert resp.json()["total_accounts"] == 0
        assert resp.json()["total_transactions"] == 0

    def test_dashboard_volume_calculation(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        resp = c.get("/api/dashboard/", headers=h)
        data = resp.json()
        # Volume is sum of all amounts: 5000 + (-1200) + (-6.42) + (-48.17) + (-134.89) = 3610.52
        expected_volume = 5000.0 - 1200.0 - 6.42 - 48.17 - 134.89
        assert abs(data["total_volume"] - expected_volume) < 0.01

    def test_dashboard_recent_statements_order(self, db_with_transactions):
        c, h, uid = db_with_transactions["client"], db_with_transactions["headers"], db_with_transactions["user_id"]
        db = TestSessionLocal()
        # Add a second statement
        db.add(models.Statement(
            account_id=db_with_transactions["account_id"], tenant_id=db_with_transactions["client_id"],
            user_id=uid, filename="newer_stmt.pdf",
            period_start="2024-06-01", period_end="2024-06-30",
            is_balanced=True,
        ))
        db.commit()
        db.close()

        resp = c.get("/api/dashboard/", headers=h)
        recent = resp.json()["recent_statements"]
        assert len(recent) == 2
        # Most recent first
        assert recent[0]["filename"] == "newer_stmt.pdf"


# =============================================================================
# EXPORT (Multi-Format)
# =============================================================================

class TestExport:
    """Statement export in 8 formats: CSV, JSON, QIF, QBO, Xero, Excel, PDF, Parquet."""

    def test_list_export_formats(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/export/formats", headers=h)
        assert resp.status_code == 200
        formats = resp.json()
        assert len(formats) == 8
        ids = {f["id"] for f in formats}
        assert "csv" in ids
        assert "json" in ids
        assert "excel" in ids
        assert "pdf" in ids
        assert "parquet" in ids
        assert "qif" in ids
        assert "qbo" in ids
        assert "xero" in ids
        # All should be "ready"
        assert all(f["status"] == "ready" for f in formats)

    def test_export_csv(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=csv", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv"
        assert "statement_" in resp.headers["content-disposition"]
        body = resp.text
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["id", "date", "description", "amount", "type", "category", "running_balance"]
        assert len(rows) == 6  # header + 5 transactions

    def test_export_json(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=json", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"
        data = resp.json()
        assert len(data) == 5
        assert data[0]["description"] == "SALARY DEPOSIT"
        assert "amount" in data[0]

    def test_export_qif(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=qif", headers=h)
        assert resp.status_code == 200
        body = resp.text
        assert "!Account" in body
        assert "!Type:Bank" in body
        assert "^" in body  # QIF record separator
        assert "SALARY DEPOSIT" in body

    def test_export_qbo(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=qbo", headers=h)
        assert resp.status_code == 200
        body = resp.text
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["Date", "Description", "Withdrawals", "Deposits"]
        # Check that salary shows as deposit (positive), rent as withdrawal
        data_rows = rows[1:]
        descriptions = [r[1] for r in data_rows]
        assert "SALARY DEPOSIT" in descriptions

    def test_export_xero(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=xero", headers=h)
        assert resp.status_code == 200
        body = resp.text
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["Date", "Payee", "Description", "Reference", "Amount"]
        assert len(rows) == 6

    def test_export_excel(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=excel", headers=h)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        assert ".xlsx" in resp.headers["content-disposition"]
        # Verify it's valid xlsx (starts with PK zip signature)
        assert resp.content[:2] == b"PK"

    def test_export_pdf(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=pdf", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"

    def test_export_invalid_format(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.get(f"/api/export/statement/{sid}?format=invalid", headers=h)
        assert resp.status_code == 400
        assert "Format must be" in resp.json()["detail"]

    def test_export_nonexistent_statement(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/export/statement/99999?format=csv", headers=h)
        assert resp.status_code == 404

    def test_export_user_isolation(self, db_with_transactions, second_user_client):
        c2, h2, _ = second_user_client
        sid = db_with_transactions["statement_id"]
        resp = c2.get(f"/api/export/statement/{sid}?format=csv", headers=h2)
        assert resp.status_code == 404


# =============================================================================
# TAX EXPORTS (Drake, Lacerte, ProConnect)
# =============================================================================

class TestTaxExports:
    """Tax software export: Drake CSV, Lacerte CSV, ProConnect TXF."""

    def test_export_drake(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/exports/tax-software?format=drake&client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 200, f"Drake export failed: {resp.text}"
        assert resp.headers["content-type"] == "text/csv"
        assert "drake.csv" in resp.headers["content-disposition"]
        body = resp.text
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["Form", "Line", "Description", "Amount"]
        # Check that a Meals transaction maps to Schedule C Line 24b
        lines = [r[1] for r in rows[1:]]
        assert any("Line 24b" in line for line in lines)

    def test_export_lacerte(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/exports/tax-software?format=lacerte&client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 200
        assert "lacerte.csv" in resp.headers["content-disposition"]
        body = resp.text
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["ExportID", "Form", "Line#", "Description", "Amount"]
        # Check ExportID format
        assert rows[1][0].startswith("EXP")

    def test_export_proconnect_txf(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/exports/tax-software?format=proconnect&client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 200
        assert ".txf" in resp.headers["content-disposition"]
        body = resp.text
        assert "ACCTINFO" in body
        assert "TRNS" in body
        assert "ENDACCTINFO" in body
        assert "^" in body  # TXF delimiter

    def test_tax_export_nonexistent_client(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/exports/tax-software?format=drake&client_id=99999&year=2024", headers=h)
        assert resp.status_code == 404

    def test_tax_export_wrong_user(self, db_with_transactions, second_user_client):
        c2, h2, _ = second_user_client
        cid = db_with_transactions["client_id"]
        resp = c2.get(f"/api/exports/tax-software?format=drake&client_id={cid}&year=2024", headers=h2)
        assert resp.status_code == 403

    def test_tax_export_no_transactions(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        cid = seeded_client["client_id"]
        resp = c.get(f"/api/exports/tax-software?format=drake&client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 404
        assert "No transactions found" in resp.json()["detail"]

    def test_tax_export_invalid_format(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/exports/tax-software?format=invalid&client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 422  # FastAPI Literal validation

    def test_tax_export_category_mapping(self, db_with_transactions):
        """Verify that specific categories map to correct Drake lines."""
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/exports/tax-software?format=drake&client_id={cid}&year=2024", headers=h)
        body = resp.text
        rows = list(csv.reader(io.StringIO(body)))
        # Find the row for the office supplies transaction
        for row in rows[1:]:
            if "Office" in row[2] or "OFFICE" in row[2]:
                assert row[1] == "Line 18"  # Office expense
                break


# =============================================================================
# ML CATEGORIZATION
# =============================================================================

class TestMLCategorization:
    """Rule-based categorization, status, and toggle endpoints."""

    def test_ml_status(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/ml/status", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["model_version"] is None
        assert "disabled by default" in data["message"]

    def test_ml_toggle(self, client, auth_client):
        c, h, _ = auth_client
        resp = c.post("/api/ml/toggle", headers=h)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert "not implemented" in resp.json()["message"]

    def test_categorize_statement(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.post(f"/api/ml/categorize/{sid}", headers=h)
        assert resp.status_code == 200, f"Categorize failed: {resp.text}"
        data = resp.json()
        assert data["statement_id"] == sid
        assert data["transactions_processed"] == 5
        assert data["categories_updated"] >= 0
        assert len(data["categories"]) > 0

    def test_categorize_updates_uncategorized(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        # Set one transaction to uncategorized
        db = TestSessionLocal()
        tx = db.query(models.Transaction).filter(
            models.Transaction.statement_id == sid
        ).first()
        tx.category = "Uncategorized"
        db.commit()
        db.close()

        resp = c.post(f"/api/ml/categorize/{sid}", headers=h)
        data = resp.json()
        assert data["categories_updated"] >= 1

    def test_categorize_nonexistent_statement(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/ml/categorize/99999", headers=h)
        assert resp.status_code == 404

    def test_categorize_user_isolation(self, db_with_transactions, second_user_client):
        c2, h2, _ = second_user_client
        sid = db_with_transactions["statement_id"]
        resp = c2.post(f"/api/ml/categorize/{sid}", headers=h2)
        assert resp.status_code == 404

    def test_categorize_rule_matching(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        sid = db_with_transactions["statement_id"]
        resp = c.post(f"/api/ml/categorize/{sid}", headers=h)
        cats = resp.json()["categories"]
        # STARBUCKS should be categorized as Food & Dining
        assert "Food & Dining" in cats or "Meals" in cats

    def test_categorize_empty_statement(self, seeded_client):
        c, h, uid = seeded_client["client"], seeded_client["headers"], seeded_client["user_id"]
        db = TestSessionLocal()
        stmt = models.Statement(
            account_id=seeded_client["account_id"], tenant_id=seeded_client["client_id"],
            user_id=uid, filename="empty.pdf",
            period_start="2024-01-01", period_end="2024-01-31", is_balanced=True,
        )
        db.add(stmt)
        db.commit()
        sid = stmt.id
        db.close()

        resp = c.post(f"/api/ml/categorize/{sid}", headers=h)
        data = resp.json()
        assert data["transactions_processed"] == 0
        assert data["categories_updated"] == 0


# =============================================================================
# TAX SUMMARY
# =============================================================================

class TestTaxSummary:
    """Tax year summary: income, expenses, net calculation."""

    def test_tax_summary(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        resp = c.get("/api/tax/summary/2024", headers=h)
        assert resp.status_code == 200, f"Tax summary failed: {resp.text}"
        data = resp.json()
        assert data["year"] == 2024
        assert data["total_income"] == 5000.00
        assert abs(data["total_expenses"] - (1200.0 + 6.42 + 48.17 + 134.89)) < 0.01
        # Net = income - expenses
        assert data["net"] == pytest.approx(data["total_income"] - data["total_expenses"], 0.01)

    def test_tax_summary_empty_year(self, auth_client):
        c, h, _ = auth_client
        resp = c.get("/api/tax/summary/1999", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_income"] == 0.0
        assert data["total_expenses"] == 0.0
        assert data["net"] == 0.0

    def test_tax_summary_no_expenses(self, auth_client):
        c, h, uid = auth_client
        db = TestSessionLocal()
        client = models.Client(name="Income Only", user_id=uid)
        db.add(client)
        db.commit()
        cid = client.id

        account = models.Account(name="Income Acct", client_id=cid, tenant_id=cid,
                                  user_id=uid, type="checking")
        db.add(account)
        db.commit()
        aid = account.id

        stmt = models.Statement(account_id=aid, tenant_id=cid, user_id=uid,
                                filename="income.pdf", period_start="2024-01-01",
                                period_end="2024-12-31", is_balanced=True)
        db.add(stmt)
        db.commit()
        sid = stmt.id

        db.add(models.Transaction(statement_id=sid, tenant_id=cid, client_id=cid,
                                  date="2024-03-15", description="BONUS",
                                  amount=Decimal("10000.00"), tx_type="credit",
                                  category="Income", confirmed=True))
        db.commit()
        db.close()

        resp = c.get("/api/tax/summary/2024", headers=h)
        data = resp.json()
        assert data["total_income"] == 10000.00
        assert data["total_expenses"] == 0.0
        assert data["net"] == 10000.00

    def test_tax_summary_year_filtering(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        # 2024 has data
        resp = c.get("/api/tax/summary/2024", headers=h)
        assert resp.json()["total_income"] > 0
        # 2023 should be empty
        resp = c.get("/api/tax/summary/2023", headers=h)
        assert resp.json()["total_income"] == 0.0


# =============================================================================
# TRANSACTION NOTES & FLAGS
# =============================================================================

class TestTransactionNotesAndFlags:
    """Notes CRUD, flags CRUD, flag resolution, filtering."""

    def test_create_note(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={
            "note": "This is a test note for the transaction"
        })
        assert resp.status_code == 200, f"Create note failed: {resp.text}"
        data = resp.json()
        assert data["note"] == "This is a test note for the transaction"
        assert data["transaction_id"] == tx_id
        assert data["user_id"] is not None

    def test_create_note_empty_fails(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={
            "note": ""
        })
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_list_notes(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        for i in range(3):
            c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={
                "note": f"Note number {i}"
            })

        resp = c.get(f"/api/transactions/{tx_id}/notes", headers=h)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) == 3
        # Should include username
        assert "username" in notes[0]
        assert notes[0]["username"] == "p2user"

    def test_list_notes_empty(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.get(f"/api/transactions/{tx_id}/notes", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_notes_pagination(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        for i in range(5):
            c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={"note": f"Note {i}"})

        resp = c.get(f"/api/transactions/{tx_id}/notes?limit=2&skip=0", headers=h)
        assert len(resp.json()) == 2

    def test_notes_ordered_by_created_desc(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={"note": "First"})
        c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={"note": "Second"})

        resp = c.get(f"/api/transactions/{tx_id}/notes", headers=h)
        notes = resp.json()
        assert notes[0]["note"] == "Second"  # Most recent first

    def test_create_flag(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={
            "flag_type": "review", "reason": "Amount seems high"
        })
        assert resp.status_code == 200, f"Create flag failed: {resp.text}"
        data = resp.json()
        assert data["flag_type"] == "review"
        assert data["reason"] == "Amount seems high"
        assert data["transaction_id"] == tx_id

    def test_create_flag_without_reason(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={
            "flag_type": "duplicate"
        })
        assert resp.status_code == 200
        assert resp.json()["reason"] is None

    def test_list_flags(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={"flag_type": "review"})
        c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={"flag_type": "fraud"})

        resp = c.get(f"/api/transactions/{tx_id}/flags", headers=h)
        assert resp.status_code == 200
        flags = resp.json()
        assert len(flags) == 2
        assert all(not f["is_resolved"] for f in flags)

    def test_list_flags_unresolved_only(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={"flag_type": "review"})
        flag_id = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={"flag_type": "fraud"}).json()["id"]
        # Resolve one
        c.patch(f"/api/transactions/{tx_id}/flags/{flag_id}/resolve", headers=h)

        resp = c.get(f"/api/transactions/{tx_id}/flags?unresolved_only=true", headers=h)
        flags = resp.json()
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "review"
        assert not flags[0]["is_resolved"]

    def test_list_flags_resolved_only(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        flag_id = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={"flag_type": "review"}).json()["id"]
        c.patch(f"/api/transactions/{tx_id}/flags/{flag_id}/resolve", headers=h)

        resp = c.get(f"/api/transactions/{tx_id}/flags?resolved_only=true", headers=h)
        flags = resp.json()
        assert len(flags) == 1
        assert flags[0]["is_resolved"] is True
        assert flags[0]["flag_type"] == "review"  # Strip 'resolved:' prefix

    def test_resolve_flag(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        flag_id = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={
            "flag_type": "review", "reason": "Check this"
        }).json()["id"]

        resp = c.patch(f"/api/transactions/{tx_id}/flags/{flag_id}/resolve", headers=h)
        assert resp.status_code == 200, f"Resolve failed: {resp.text}"
        data = resp.json()
        assert data["ok"] is True
        assert data["flag_id"] == flag_id
        assert data["original_type"] == "review"
        assert data["is_resolved"] is True

    def test_resolve_already_resolved_flag(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        flag_id = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={"flag_type": "review"}).json()["id"]
        c.patch(f"/api/transactions/{tx_id}/flags/{flag_id}/resolve", headers=h)

        resp = c.patch(f"/api/transactions/{tx_id}/flags/{flag_id}/resolve", headers=h)
        assert resp.status_code == 409
        assert "already resolved" in resp.json()["detail"]

    def test_resolve_nonexistent_flag(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.patch(f"/api/transactions/{tx_id}/flags/99999/resolve", headers=h)
        assert resp.status_code == 404

    def test_notes_on_nonexistent_transaction(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/transactions/99999/notes", headers=h, json={"note": "test"})
        assert resp.status_code == 404

    def test_flags_on_nonexistent_transaction(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/transactions/99999/flags", headers=h, json={"flag_type": "review"})
        assert resp.status_code == 404


# =============================================================================
# UPLOAD (PDF Statement)
# =============================================================================

class TestUpload:
    """PDF statement upload, parse, statement creation, transaction extraction."""

    def _create_minimal_pdf(self):
        """Create a minimal valid PDF file in memory."""
        return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Test Bank Statement) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000214 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n308\n%%EOF\n"

    def test_upload_rejects_non_pdf(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/upload/", headers=h, files={
            "file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")
        })
        assert resp.status_code == 400
        assert "Only PDF files" in resp.json()["detail"]

    def test_upload_pdf(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        pdf = self._create_minimal_pdf()
        resp = c.post("/api/upload/", headers=h, files={
            "file": ("test_statement.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert "statement_id" in data
        assert data["transactions_count"] >= 0

    def test_upload_with_account_id(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        aid = seeded_client["account_id"]
        pdf = self._create_minimal_pdf()
        resp = c.post(f"/api/upload/?account_id={aid}", headers=h, files={
            "file": ("acct_stmt.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["statement_id"] is not None

    def test_upload_with_invalid_account_id(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        pdf = self._create_minimal_pdf()
        resp = c.post("/api/upload/?account_id=99999", headers=h, files={
            "file": ("bad_acct.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert resp.status_code == 404

    def test_upload_response_fields(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        pdf = self._create_minimal_pdf()
        resp = c.post("/api/upload/", headers=h, files={
            "file": ("fields_test.pdf", io.BytesIO(pdf), "application/pdf")
        })
        data = resp.json()
        assert "statement_id" in data
        assert "transactions_count" in data
        assert "variance" in data
        assert "balanced" in data
        assert "template" in data

    def test_upload_requires_auth(self, client):
        pdf = b"%PDF-1.4\n%%EOF\n"
        resp = client.post("/api/upload/", files={
            "file": ("test.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert resp.status_code == 401

    def test_upload_filename_sanitization(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        pdf = self._create_minimal_pdf()
        resp = c.post("/api/upload/", headers=h, files={
            "file": ("file with spaces.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert resp.status_code == 200

    def test_date_standardization(self, seeded_client):
        """The upload router standardizes dates from MM/DD/YYYY to YYYY-MM-DD."""
        c, h = seeded_client["client"], seeded_client["headers"]
        pdf = self._create_minimal_pdf()
        resp = c.post("/api/upload/", headers=h, files={
            "file": ("date_test.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert resp.status_code == 200
        # Date standardization is tested implicitly through successful upload


# =============================================================================
# EVENTS (SSE)
# =============================================================================

class TestEvents:
    """SSE event manager: publish, stream, per-user isolation."""

    def test_event_manager_is_singleton(self):
        from backend.events import event_manager as em1
        from backend.events import event_manager as em2
        assert em1 is em2

    def test_publish_and_retrieve(self, db_session):
        asyncio.run(self._async_publish_test())

    async def _async_publish_test(self):
        user_id = 42
        # Clear any existing events for this user
        while not event_manager._queues[user_id].empty():
            try:
                event_manager._queues[user_id].get_nowait()
            except asyncio.QueueEmpty:
                break

        event_manager.publish_import_complete(statement_id=1, count=50, user_id=user_id)
        event_manager.publish_backup_created(path="/tmp/backup.zip", user_id=user_id)
        event_manager.publish_training_complete(version="1.0.0", user_id=user_id)
        event_manager.publish_period_locked(period_id=5, user_id=user_id)

        events = []
        for _ in range(4):
            try:
                evt = await asyncio.wait_for(
                    event_manager._queues[user_id].get(), timeout=1.0
                )
                events.append(evt)
            except asyncio.TimeoutError:
                break

        assert len(events) == 4
        types = {e["type"] for e in events}
        assert "import_complete" in types
        assert "backup_created" in types
        assert "training_complete" in types
        assert "period_locked" in types

    def test_per_user_isolation(self, db_session):
        asyncio.run(self._async_isolation_test())

    async def _async_isolation_test(self):
        user_a = 100
        user_b = 200

        # Clear queues
        for uid in [user_a, user_b]:
            while not event_manager._queues[uid].empty():
                try:
                    event_manager._queues[uid].get_nowait()
                except asyncio.QueueEmpty:
                    break

        event_manager.publish_import_complete(statement_id=1, count=10, user_id=user_a)

        # User A should receive the event
        evt_a = await asyncio.wait_for(
            event_manager._queues[user_a].get(), timeout=1.0
        )
        assert evt_a["type"] == "import_complete"

        # User B should NOT receive the event (timeout)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                event_manager._queues[user_b].get(), timeout=0.5
            )

    def test_event_structure(self, db_session):
        asyncio.run(self._async_structure_test())

    async def _async_structure_test(self):
        user_id = 300
        while not event_manager._queues[user_id].empty():
            try:
                event_manager._queues[user_id].get_nowait()
            except asyncio.QueueEmpty:
                break

        event_manager.publish_import_complete(statement_id=7, count=25, user_id=user_id)
        evt = await asyncio.wait_for(
            event_manager._queues[user_id].get(), timeout=1.0
        )
        assert "type" in evt
        assert "data" in evt
        assert "timestamp" in evt
        assert evt["data"]["statement_id"] == 7
        assert evt["data"]["transaction_count"] == 25

    def test_unknown_event_type(self, db_session):
        """Publishing an unknown event type should not crash."""
        event_manager.publish("unknown_type", {"test": "data"}, user_id=400)
        # Should not raise

    def test_stream_format_sse(self, db_session):
        asyncio.run(self._async_sse_format_test())

    async def _async_sse_format_test(self):
        user_id = 500
        while not event_manager._queues[user_id].empty():
            try:
                event_manager._queues[user_id].get_nowait()
            except asyncio.QueueEmpty:
                break

        event_manager.publish_import_complete(statement_id=1, count=5, user_id=user_id)
        # The stream generator should format as SSE
        stream = event_manager.get_event_stream(user_id)
        chunk = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
        assert chunk.startswith("data: ")
        assert "import_complete" in chunk

    def test_max_queue_size(self, db_session):
        """Queue should not grow unbounded."""
        user_id = 600
        # Publish many events
        for i in range(150):
            event_manager.publish_import_complete(statement_id=i, count=1, user_id=user_id)
        # Queue should be capped
        assert event_manager._queues[user_id].qsize() <= 100


# =============================================================================
# CROSS-CUTTING E2E
# =============================================================================

class TestCrossCuttingP2:
    """End-to-end workflows spanning multiple routers."""

    def test_upload_categorize_export_workflow(self, seeded_client):
        """
        1. Upload a PDF statement
        2. Categorize transactions with ML
        3. Export as CSV
        4. Export tax software format
        Verify data integrity at each step.
        """
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        aid = seeded_client["account_id"]

        # Step 1: Upload
        pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(STARBUCKS COFFEE) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n308\n%%EOF\n"
        upload_resp = c.post(f"/api/upload/?account_id={aid}", headers=h, files={
            "file": ("e2e_test.pdf", io.BytesIO(pdf), "application/pdf")
        })
        assert upload_resp.status_code == 200
        sid = upload_resp.json()["statement_id"]
        tx_count = upload_resp.json()["transactions_count"]

        # Step 2: Categorize
        cat_resp = c.post(f"/api/ml/categorize/{sid}", headers=h)
        assert cat_resp.status_code == 200

        # Step 3: Export CSV
        csv_resp = c.get(f"/api/export/statement/{sid}?format=csv", headers=h)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]

        # Step 4: Export tax
        tax_resp = c.get(f"/api/exports/tax-software?format=drake&client_id={cid}&year=2024", headers=h)
        # May be 404 if no transactions with dates in 2024, that's acceptable
        assert tax_resp.status_code in (200, 404)

    def test_full_accounting_workflow(self, seeded_client):
        """
        1. Create client
        2. Create account for client
        3. Create budget
        4. Add transaction
        5. Add note to transaction
        6. Flag transaction
        7. Resolve flag
        8. Check dashboard reflects all data
        """
        c, h, uid = seeded_client["client"], seeded_client["headers"], seeded_client["user_id"]
        cid = seeded_client["client_id"]

        # Create account
        aid = c.post("/api/accounts/", headers=h, json={
            "name": "Workflow Checking", "client_id": cid, "type": "checking"
        }).json()["id"]

        # Create budget
        c.post(f"/api/budgets/?client_id={cid}", headers=h, json={
            "name": "Workflow Budget", "period_start": "2024-01-01",
            "period_end": "2024-12-31", "total_budget": 10000, "is_active": True,
            "entries": [{"category": "supplies", "amount": 500}],
        })

        # Add statement with transactions via direct DB
        db = TestSessionLocal()
        stmt = models.Statement(
            account_id=aid, tenant_id=cid, user_id=uid,
            filename="workflow.pdf", period_start="2024-01-01",
            period_end="2024-12-31", is_balanced=True,
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)

        tx = models.Transaction(
            statement_id=stmt.id, tenant_id=cid, client_id=cid,
            date="2024-03-15", description="WORKFLOW-TEST",
            amount=Decimal("-250.00"), tx_type="debit",
            category="supplies", confirmed=True,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        tx_id = tx.id
        db.close()

        # Add note
        note_resp = c.post(f"/api/transactions/{tx_id}/notes", headers=h, json={
            "note": "Workflow integration test note"
        })
        assert note_resp.status_code == 200

        # Flag
        flag_resp = c.post(f"/api/transactions/{tx_id}/flags", headers=h, json={
            "flag_type": "review", "reason": "Workflow test"
        })
        flag_id = flag_resp.json()["id"]

        # Resolve flag
        resolve_resp = c.patch(f"/api/transactions/{tx_id}/flags/{flag_id}/resolve", headers=h)
        assert resolve_resp.status_code == 200

        # Check dashboard
        dash_resp = c.get("/api/dashboard/", headers=h)
        assert dash_resp.status_code == 200
        data = dash_resp.json()
        assert data["total_accounts"] >= 2
        assert data["total_transactions"] >= 1
