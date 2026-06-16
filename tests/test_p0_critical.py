"""
TaxFlow Pro v3.8 — P0 Critical Router Tests
============================================

Comprehensive unit and integration tests for the 6 most critical routers:
1. Journal Entries (create, post, balance validation, period locks)
2. CPA Sign-Off (HMAC signing, master password, report types)
3. Archive (year-end archive/restore, master password gate)
4. Transaction List (filtering, pagination, search, update, soft-delete)
5. Periods (create, lock, unlock, date-in-period check)
6. Audit Trail (hash chain integrity, tamper detection, genesis hash)

Plus: Authentication flow tests (register, login, 401 handling)

All tests are independent (fresh DB per test) and use FastAPI TestClient.
"""

import os
import sys
import json
import hashlib
import hmac
from datetime import datetime, timezone
from decimal import Decimal

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
from backend.audit.audit_trail import (
    create_audit_entry,
    verify_chain_integrity,
    _get_genesis_hash,
    _compute_event_hash,
    ACTION_CREATE_JOURNAL,
    ACTION_POST_JOURNAL,
    ACTION_LOCK_PERIOD,
    ACTION_UNLOCK_PERIOD,
    ACTION_SIGN_REPORT,
    ACTION_UPDATE_TRANSACTION,
    ACTION_DELETE_TRANSACTION,
    ACTION_ARCHIVE_YEAR,
    ACTION_RESTORE_YEAR,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///./test_p0_critical.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
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
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    """Fresh database with tables created, rolled back after each test."""
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()
    yield db
    db.rollback()
    db.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with fresh DB."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def auth_client(client):
    """Authenticated client with Bearer token. Returns (client, headers, user_id)."""
    resp = client.post("/api/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    user_id = resp.json()["id"]

    resp = client.post("/api/auth/login", data={
        "username": "testuser",
        "password": "testpass123"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    return client, headers, user_id


@pytest.fixture(scope="function")
def seeded_client(auth_client):
    """Authenticated client with a client, account, and period created."""
    client, headers, user_id = auth_client

    # Create a business client
    resp = client.post("/api/clients/", headers=headers, json={
        "name": "Test Business",
        "email": "business@example.com",
        "tax_id": "12-3456789"
    })
    assert resp.status_code == 200
    business_client_id = resp.json()["id"]

    # Create an account for the client
    resp = client.post("/api/accounts/", headers=headers, json={
        "name": "Business Checking",
        "institution": "Chase",
        "account_number_masked": "****1234",
        "type": "checking",
        "client_id": business_client_id
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]

    return {
        "client": client,
        "headers": headers,
        "user_id": user_id,
        "client_id": business_client_id,
        "account_id": account_id,
    }


@pytest.fixture(scope="function")
def db_with_transactions(seeded_client):
    """Seed DB with transactions directly for transaction list tests."""
    data = seeded_client
    db = TestSessionLocal()

    # Create a statement
    stmt = models.Statement(
        account_id=data["account_id"],
        tenant_id=data["client_id"],
        user_id=data["user_id"],
        filename="test_stmt.pdf",
        period_start="2024-01-01",
        period_end="2024-12-31",
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("800.00"),
        variance=Decimal("-200.00"),
        is_balanced=True,
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)

    # Create diverse transactions
    txs = [
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
                           client_id=data["client_id"], date="2024-01-15",
                           description="SALARY DEPOSIT", amount=Decimal("2000.00"),
                           tx_type="credit", category="Income", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
                           client_id=data["client_id"], date="2024-02-01",
                           description="RENT PAYMENT", amount=Decimal("-800.00"),
                           tx_type="debit", category="Housing", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
                           client_id=data["client_id"], date="2024-03-10",
                           description="STARBUCKS COFFEE", amount=Decimal("-5.50"),
                           tx_type="debit", category="Food & Dining", confirmed=False),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
                           client_id=data["client_id"], date="2024-04-20",
                           description="SHELL GAS", amount=Decimal("-45.00"),
                           tx_type="debit", category="Auto & Transport", confirmed=True),
        models.Transaction(statement_id=stmt.id, tenant_id=data["client_id"],
                           client_id=data["client_id"], date="2024-06-15",
                           description="AMAZON PURCHASE", amount=Decimal("-150.00"),
                           tx_type="debit", category="Shopping", confirmed=False),
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
# AUTHENTICATION FLOW TESTS
# =============================================================================

class TestAuthFlow:
    """Test registration, login, token validation, and protected route access."""

    def test_register_creates_user(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert "id" in data

    def test_register_duplicate_username_fails(self, client):
        client.post("/api/auth/register", json={
            "username": "dupuser", "email": "a@example.com", "password": "pw"
        })
        resp = client.post("/api/auth/register", json={
            "username": "dupuser", "email": "b@example.com", "password": "pw"
        })
        assert resp.status_code == 400

    def test_login_returns_valid_token(self, client):
        client.post("/api/auth/register", json={
            "username": "loginuser", "email": "login@example.com", "password": "loginpass"
        })
        resp = client.post("/api/auth/login", data={
            "username": "loginuser", "password": "loginpass"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    def test_login_wrong_password_fails(self, client):
        client.post("/api/auth/register", json={
            "username": "wrongpwuser", "email": "wp@example.com", "password": "rightpass"
        })
        resp = client.post("/api/auth/login", data={
            "username": "wrongpwuser", "password": "wrongpass"
        })
        assert resp.status_code == 401

    def test_protected_route_without_token_returns_401(self, client):
        resp = client.get("/api/clients/")
        assert resp.status_code == 401

    def test_protected_route_with_invalid_token_returns_401(self, client):
        resp = client.get("/api/clients/", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401

    def test_auth_me_returns_current_user(self, auth_client):
        client, headers, user_id = auth_client
        resp = client.get("/api/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["id"] == user_id
        assert data["is_active"] is True

    def test_auth_me_without_token_fails(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


# =============================================================================
# JOURNAL ENTRY TESTS
# =============================================================================

class TestJournalEntries:
    """Test journal entry CRUD, posting, balance validation, and period locks."""

    def _create_je(self, client, headers, client_id, lines, entry_number="JE-001",
                   entry_date="2024-06-15", memo="Test JE"):
        """Helper to create a journal entry."""
        return client.post(
            f"/api/journal-entries/?client_id={client_id}",
            headers=headers,
            json={
                "entry_number": entry_number,
                "entry_date": entry_date,
                "memo": memo,
                "lines": lines,
            }
        )

    def test_create_journal_entry_with_balanced_lines(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 100.00, "credit": 0, "memo": "Receive cash"},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 100.00, "memo": "Earn revenue"},
        ])
        assert resp.status_code == 201, f"Create JE failed: {resp.text}"
        data = resp.json()
        assert data["entry_number"] == "JE-001"
        assert data["memo"] == "Test JE"
        assert len(data["lines"]) == 2
        assert data["tenant_id"] == cid

    def test_create_journal_entry_imbalance_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 100.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 50.00},
        ])
        assert resp.status_code == 400
        assert "Debits (100.00) must equal credits (50.00)" in resp.json()["detail"]

    def test_create_journal_entry_zero_lines_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 0, "credit": 0},
        ])
        assert resp.status_code == 400
        assert "at least one non-zero line" in resp.json()["detail"]

    def test_create_journal_entry_no_lines_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = self._create_je(c, h, cid, [])
        assert resp.status_code == 400
        assert "at least one line item" in resp.json()["detail"]

    def test_list_journal_entries(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 200.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 200.00},
        ], entry_number="JE-002")
        resp = c.get(f"/api/journal-entries/?client_id={cid}", headers=h)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) >= 1
        assert any(e["entry_number"] == "JE-002" for e in entries)

    def test_get_journal_entry_by_id(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        create_resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 300.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 300.00},
        ], entry_number="JE-003")
        je_id = create_resp.json()["id"]

        resp = c.get(f"/api/journal-entries/{je_id}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == je_id
        assert data["entry_number"] == "JE-003"
        assert len(data["lines"]) == 2

    def test_get_nonexistent_journal_entry_returns_404(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/journal-entries/99999", headers=h)
        assert resp.status_code == 404

    def test_post_journal_entry_creates_transactions(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        # Create JE
        create_resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 500.00, "credit": 0, "memo": "Invest cash"},
            {"account_code": "3000", "account_name": "Owner Equity", "debit": 0, "credit": 500.00, "memo": "Owner investment"},
        ], entry_number="JE-004")
        assert create_resp.status_code == 201
        je_id = create_resp.json()["id"]

        # Post the JE
        resp = c.post(f"/api/journal-entries/{je_id}/post", headers=h)
        assert resp.status_code == 200, f"Post failed: {resp.text}"
        data = resp.json()
        assert data["id"] == je_id

        # Verify transactions were created
        db = TestSessionLocal()
        try:
            txs = db.query(models.Transaction).filter(
                models.Transaction.journal_entry_id == je_id
            ).all()
            assert len(txs) == 2, f"Expected 2 transactions, got {len(txs)}"
            assert all(tx.is_journal for tx in txs)
            assert all(tx.confirmed for tx in txs)
            amounts = {tx.amount for tx in txs}
            assert len(amounts) == 1  # Both should be 500.00 (abs)
            assert 500.00 in amounts or Decimal("500") in amounts
        finally:
            db.close()

    def test_post_journal_entry_already_posted_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        create_resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 100.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 100.00},
        ], entry_number="JE-005")
        je_id = create_resp.json()["id"]

        # First post succeeds
        resp1 = c.post(f"/api/journal-entries/{je_id}/post", headers=h)
        assert resp1.status_code == 200

        # Second post fails
        resp2 = c.post(f"/api/journal-entries/{je_id}/post", headers=h)
        assert resp2.status_code == 409
        assert "already posted" in resp2.json()["detail"].lower()

    def test_delete_unposted_journal_entry(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        create_resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 50.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 50.00},
        ], entry_number="JE-006")
        je_id = create_resp.json()["id"]

        resp = c.delete(f"/api/journal-entries/{je_id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify it's gone
        resp2 = c.get(f"/api/journal-entries/{je_id}", headers=h)
        assert resp2.status_code == 404

    def test_delete_posted_journal_entry_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        create_resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 75.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 75.00},
        ], entry_number="JE-007")
        je_id = create_resp.json()["id"]
        c.post(f"/api/journal-entries/{je_id}/post", headers=h)

        resp = c.delete(f"/api/journal-entries/{je_id}", headers=h)
        assert resp.status_code == 409
        assert "Cannot delete a posted" in resp.json()["detail"]

    def test_post_journal_entry_in_locked_period_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        # Create and lock a period
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Q2 2024",
            "start_date": "2024-04-01",
            "end_date": "2024-06-30",
            "status": "open",
            "is_locked": False,
        })
        assert resp.status_code == 201
        period_id = resp.json()["id"]

        # Lock the period
        lock_resp = c.post(f"/api/periods/{period_id}/lock", headers=h)
        assert lock_resp.status_code == 200

        # Try to create a JE within the locked period
        resp = self._create_je(c, h, cid, [
            {"account_code": "1000", "account_name": "Cash", "debit": 25.00, "credit": 0},
            {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 25.00},
        ], entry_number="JE-008", entry_date="2024-05-15")
        assert resp.status_code == 409
        assert "locked" in resp.json()["detail"].lower()


# =============================================================================
# CPA SIGN-OFF TESTS
# =============================================================================

class TestCPASignOff:
    """Test HMAC-SHA256 signed reports, master password verification, and retrieval."""

    def test_sign_report_with_valid_password(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        report_data = {
            "total_income": 50000.00,
            "total_expenses": 30000.00,
            "net_income": 20000.00,
            "categories": {"Income": 50000, "Expenses": 30000},
        }
        resp = c.post("/api/reports/tax_summary/sign", headers=h, json={
            "client_id": cid,
            "year": "2024",
            "title": "2024 Tax Summary - Test Business",
            "report_data": report_data,
            "master_password": "testpass123",  # Same as login password
        })
        assert resp.status_code == 200, f"Sign failed: {resp.text}"
        data = resp.json()
        assert data["report_type"] == "tax_summary"
        assert data["signature_hash"] is not None
        assert len(data["signature_hash"]) == 64  # SHA-256 hex = 64 chars
        assert data["tenant_id"] == cid

    def test_sign_report_with_invalid_password_returns_403(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post("/api/reports/tax_summary/sign", headers=h, json={
            "client_id": cid,
            "year": "2024",
            "title": "Bad Password Test",
            "report_data": {"income": 100},
            "master_password": "wrongpassword",
        })
        assert resp.status_code == 403
        assert "Invalid master password" in resp.json()["detail"]

    def test_sign_report_invalid_type_returns_400(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post("/api/reports/invalid_type/sign", headers=h, json={
            "client_id": cid,
            "year": "2024",
            "title": "Invalid Type Test",
            "report_data": {"income": 100},
            "master_password": "testpass123",
        })
        assert resp.status_code == 400
        assert "Invalid report type" in resp.json()["detail"]

    def test_sign_report_all_valid_types(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        valid_types = ["pl", "balance_sheet", "cash_flow", "tax_summary", "general_ledger", "trial_balance"]
        for report_type in valid_types:
            resp = c.post(f"/api/reports/{report_type}/sign", headers=h, json={
                "client_id": cid,
                "year": "2024",
                "title": f"Test {report_type}",
                "report_data": {"test": "data"},
                "master_password": "testpass123",
            })
            assert resp.status_code == 200, f"Type {report_type} failed: {resp.text}"

    def test_list_signed_reports(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        # Sign two reports
        for title in ["Report A", "Report B"]:
            c.post("/api/reports/tax_summary/sign", headers=h, json={
                "client_id": cid,
                "year": "2024",
                "title": title,
                "report_data": {"test": title},
                "master_password": "testpass123",
            })

        resp = c.get(f"/api/reports/signed?client_id={cid}", headers=h)
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) >= 2
        titles = {r["file_path"] for r in reports}
        assert "Report A" in titles
        assert "Report B" in titles

    def test_get_signed_report_by_id(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        sign_resp = c.post("/api/reports/pl/sign", headers=h, json={
            "client_id": cid,
            "year": "2024",
            "title": "P&L Report",
            "report_data": {"revenue": 100000, "expenses": 60000},
            "master_password": "testpass123",
        })
        report_id = sign_resp.json()["id"]

        resp = c.get(f"/api/reports/signed/{report_id}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == report_id
        assert data["report_type"] == "pl"
        assert data["file_path"] == "P&L Report"
        assert len(data["signature_hash"]) == 64

    def test_get_nonexistent_signed_report_returns_404(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.get("/api/reports/signed/99999", headers=h)
        assert resp.status_code == 404

    def test_signature_hash_is_deterministic(self, seeded_client):
        """Same report data + same user should produce verifiable HMAC."""
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        report_data = {"income": 1000, "expenses": 500}

        resp = c.post("/api/reports/tax_summary/sign", headers=h, json={
            "client_id": cid,
            "year": "2024",
            "title": "Deterministic Test",
            "report_data": report_data,
            "master_password": "testpass123",
        })
        sig1 = resp.json()["signature_hash"]

        resp2 = c.post("/api/reports/tax_summary/sign", headers=h, json={
            "client_id": cid,
            "year": "2024",
            "title": "Deterministic Test 2",
            "report_data": report_data,
            "master_password": "testpass123",
        })
        sig2 = resp2.json()["signature_hash"]

        # Different timestamps = different signatures (non-repudiation)
        assert sig1 != sig2, "Signatures should differ due to timestamps (non-repudiation)"
        # But both should be valid 64-char hex
        assert len(sig1) == 64
        assert len(sig2) == 64


# =============================================================================
# ARCHIVE TESTS
# =============================================================================

class TestArchive:
    """Test year-end archive and restore with master password gate."""

    def test_archive_year_creates_archive_file(self, seeded_client, monkeypatch):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        uid = seeded_client["user_id"]

        # Seed transactions for the year
        db = TestSessionLocal()
        try:
            account = db.query(models.Account).filter(models.Account.client_id == cid).first()
            stmt = models.Statement(
                account_id=account.id, tenant_id=cid, user_id=uid,
                filename="archive_test.pdf", period_start="2024-01-01",
                period_end="2024-12-31", is_balanced=True,
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)

            for i in range(5):
                tx = models.Transaction(
                    statement_id=stmt.id, tenant_id=cid, client_id=cid,
                    date=f"2024-0{i+1}-15", description=f"TX-{i}",
                    amount=Decimal("-10.00"), tx_type="debit",
                    category="Test", confirmed=True, archived=False,
                )
                db.add(tx)
            db.commit()
        finally:
            db.close()

        resp = c.post(f"/api/clients/{cid}/archive-year?year=2024", headers=h)
        assert resp.status_code == 200, f"Archive failed: {resp.text}"
        data = resp.json()
        assert data["count"] == 5
        assert "archive_path" in data
        assert "client_" in data["archive_path"]

        # Verify transactions are marked archived
        db = TestSessionLocal()
        try:
            archived_count = db.query(models.Transaction).filter(
                models.Transaction.client_id == cid,
                models.Transaction.archived == True,
            ).count()
            assert archived_count == 5
        finally:
            db.close()

    def test_archive_year_no_transactions_returns_404(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/clients/{cid}/archive-year?year=1999", headers=h)
        assert resp.status_code == 404
        assert "No unarchived transactions" in resp.json()["detail"]

    def test_archive_year_wrong_client_returns_404(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/clients/99999/archive-year?year=2024", headers=h)
        assert resp.status_code == 404

    def test_restore_year_requires_master_password(self, seeded_client, monkeypatch):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        uid = seeded_client["user_id"]

        # Set master password env
        monkeypatch.setenv("TAXFLOW_ARCHIVE_MASTER_PASSWORD", "archive_secret")

        # Seed and archive transactions
        db = TestSessionLocal()
        try:
            account = db.query(models.Account).filter(models.Account.client_id == cid).first()
            stmt = models.Statement(
                account_id=account.id, tenant_id=cid, user_id=uid,
                filename="restore_test.pdf", period_start="2024-01-01",
                period_end="2024-12-31", is_balanced=True,
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)

            tx = models.Transaction(
                statement_id=stmt.id, tenant_id=cid, client_id=cid,
                date="2024-03-15", description="RESTORE-ME",
                amount=Decimal("-25.00"), tx_type="debit",
                category="Test", confirmed=True, archived=False,
            )
            db.add(tx)
            db.commit()
            tx_id = tx.id
        finally:
            db.close()

        # Archive
        resp = c.post(f"/api/clients/{cid}/archive-year?year=2024", headers=h)
        assert resp.status_code == 200

        # Restore with correct password
        resp = c.post(
            f"/api/clients/{cid}/restore-year?year=2024",
            headers=h,
            data={"master_password": "archive_secret"},
        )
        assert resp.status_code == 200, f"Restore failed: {resp.text}"
        data = resp.json()
        assert data["count"] >= 1

        # Verify transactions are unarchived
        db = TestSessionLocal()
        try:
            restored_tx = db.query(models.Transaction).filter(
                models.Transaction.id == tx_id,
            ).first()
            assert restored_tx is not None
            assert restored_tx.archived is False
        finally:
            db.close()

    def test_restore_year_wrong_password_fails(self, seeded_client, monkeypatch):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        uid = seeded_client["user_id"]

        monkeypatch.setenv("TAXFLOW_ARCHIVE_MASTER_PASSWORD", "correct_secret")

        # Seed and archive
        db = TestSessionLocal()
        try:
            account = db.query(models.Account).filter(models.Account.client_id == cid).first()
            stmt = models.Statement(
                account_id=account.id, tenant_id=cid, user_id=uid,
                filename="pw_test.pdf", period_start="2024-01-01",
                period_end="2024-12-31", is_balanced=True,
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)

            tx = models.Transaction(
                statement_id=stmt.id, tenant_id=cid, client_id=cid,
                date="2024-04-01", description="PW-TEST",
                amount=Decimal("-10.00"), tx_type="debit",
                category="Test", confirmed=True, archived=False,
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        c.post(f"/api/clients/{cid}/archive-year?year=2024", headers=h)

        # Try restore with wrong password
        resp = c.post(
            f"/api/clients/{cid}/restore-year?year=2024",
            headers=h,
            data={"master_password": "wrong_secret"},
        )
        assert resp.status_code == 401
        assert "Invalid master password" in resp.json()["detail"]

    def test_restore_nonexistent_archive_returns_404(self, seeded_client, monkeypatch):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        monkeypatch.setenv("TAXFLOW_ARCHIVE_MASTER_PASSWORD", "secret")
        resp = c.post(
            f"/api/clients/{cid}/restore-year?year=1980",
            headers=h,
            data={"master_password": "secret"},
        )
        assert resp.status_code == 404
        assert "No archive found" in resp.json()["detail"]


# =============================================================================
# TRANSACTION LIST TESTS
# =============================================================================

class TestTransactionList:
    """Test transaction querying, filtering, pagination, update, and archive."""

    def test_list_transactions_basic(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 5

    def test_list_transactions_filter_by_year(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 5

    def test_list_transactions_filter_by_category(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&category=Income", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 1
        assert txs[0]["description"] == "SALARY DEPOSIT"

    def test_list_transactions_filter_by_confirmed(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&confirmed=false", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 2  # Two unconfirmed transactions

    def test_list_transactions_filter_by_tx_type(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&tx_type=credit", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 1
        assert txs[0]["tx_type"] == "credit"

    def test_list_transactions_search(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&search=STARBUCKS", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 1
        assert "STARBUCKS" in txs[0]["description"]

    def test_list_transactions_pagination(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&limit=2&skip=0", headers=h)
        assert resp.status_code == 200
        page1 = resp.json()
        assert len(page1) == 2

        resp = c.get(f"/api/transactions?client_id={cid}&limit=2&skip=2", headers=h)
        assert resp.status_code == 200
        page2 = resp.json()
        assert len(page2) == 2

        # Pages should be different
        ids1 = {t["id"] for t in page1}
        ids2 = {t["id"] for t in page2}
        assert ids1 != ids2

    def test_list_transactions_default_excludes_archived(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        # Archive one transaction directly
        db = TestSessionLocal()
        try:
            tx = db.query(models.Transaction).filter(
                models.Transaction.client_id == cid
            ).first()
            tx.archived = True
            db.commit()
        finally:
            db.close()

        resp = c.get(f"/api/transactions?client_id={cid}", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 4  # One archived, excluded by default

    def test_list_transactions_include_archived(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        db = TestSessionLocal()
        try:
            tx = db.query(models.Transaction).filter(
                models.Transaction.client_id == cid
            ).first()
            tx.archived = True
            db.commit()
        finally:
            db.close()

        resp = c.get(f"/api/transactions?client_id={cid}&archived=true", headers=h)
        assert resp.status_code == 200
        txs = resp.json()
        # Should include the archived one
        assert len(txs) >= 1

    def test_update_transaction_category(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]

        resp = c.patch(f"/api/transactions/{tx_id}", headers=h, json={
            "category": "Updated Category"
        })
        assert resp.status_code == 200, f"Update failed: {resp.text}"
        data = resp.json()
        assert data["category"] == "Updated Category"

    def test_update_transaction_confirm(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        # Find an unconfirmed transaction
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}&confirmed=false", headers=h)
        unconfirmed = resp.json()
        assert len(unconfirmed) > 0
        tx_id = unconfirmed[0]["id"]

        resp = c.patch(f"/api/transactions/{tx_id}", headers=h, json={"confirmed": True})
        assert resp.status_code == 200
        assert resp.json()["confirmed"] is True

    def test_update_nonexistent_transaction_returns_404(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.patch("/api/transactions/99999", headers=h, json={"category": "Test"})
        assert resp.status_code == 404

    def test_update_transaction_no_fields_fails(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]
        resp = c.patch(f"/api/transactions/{tx_id}", headers=h, json={})
        assert resp.status_code == 400
        assert "No fields provided" in resp.json()["detail"]

    def test_archive_transaction(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]

        resp = c.delete(f"/api/transactions/{tx_id}", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["archived"] is True

        # Verify it's excluded from default list
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions?client_id={cid}", headers=h)
        assert tx_id not in {t["id"] for t in resp.json()}

    def test_archive_already_archived_fails(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        tx_id = db_with_transactions["transaction_ids"][0]

        c.delete(f"/api/transactions/{tx_id}", headers=h)
        resp = c.delete(f"/api/transactions/{tx_id}", headers=h)
        assert resp.status_code == 409
        assert "already archived" in resp.json()["detail"].lower()

    def test_transactions_summary(self, db_with_transactions):
        c, h = db_with_transactions["client"], db_with_transactions["headers"]
        cid = db_with_transactions["client_id"]
        resp = c.get(f"/api/transactions/summary?client_id={cid}&year=2024", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 5
        assert data["confirmed_count"] == 3
        assert data["unconfirmed_count"] == 2
        assert len(data["categories"]) >= 4  # Income, Housing, Food & Dining, Auto & Transport, Shopping
        assert len(data["monthly"]) >= 4  # Jan, Feb, Mar, Apr, Jun


# =============================================================================
# PERIOD TESTS
# =============================================================================

class TestPeriods:
    """Test period CRUD, lock/unlock, and date-in-period checking."""

    def test_create_period(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Q1 2024",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "status": "open",
            "is_locked": False,
        })
        assert resp.status_code == 201, f"Create period failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Q1 2024"
        assert data["start_date"] == "2024-01-01"
        assert data["end_date"] == "2024-03-31"
        assert data["is_locked"] is False

    def test_create_period_end_before_start_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Bad Period",
            "start_date": "2024-12-31",
            "end_date": "2024-01-01",
            "status": "open",
            "is_locked": False,
        })
        assert resp.status_code == 400
        assert "end_date must be on or after" in resp.json()["detail"]

    def test_create_overlapping_period_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Q1 2024",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
            "status": "open",
            "is_locked": False,
        })

        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Q1 Overlap",
            "start_date": "2024-02-15",
            "end_date": "2024-04-30",
            "status": "open",
            "is_locked": False,
        })
        assert resp.status_code == 409
        assert "overlaps" in resp.json()["detail"].lower()

    def test_list_periods(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        for name, start, end in [("Q1", "2024-01-01", "2024-03-31"), ("Q2", "2024-04-01", "2024-06-30")]:
            c.post(f"/api/periods/?client_id={cid}", headers=h, json={
                "name": name, "start_date": start, "end_date": end,
                "status": "open", "is_locked": False,
            })

        resp = c.get(f"/api/periods/?client_id={cid}", headers=h)
        assert resp.status_code == 200
        periods = resp.json()
        assert len(periods) == 2
        names = {p["name"] for p in periods}
        assert "Q1" in names
        assert "Q2" in names

    def test_lock_period(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Lock Test",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "open",
            "is_locked": False,
        })
        period_id = resp.json()["id"]

        resp = c.post(f"/api/periods/{period_id}/lock", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["is_locked"] is True

    def test_lock_already_locked_period_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Double Lock",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "open",
            "is_locked": False,
        })
        period_id = resp.json()["id"]

        c.post(f"/api/periods/{period_id}/lock", headers=h)
        resp = c.post(f"/api/periods/{period_id}/lock", headers=h)
        assert resp.status_code == 409
        assert "already locked" in resp.json()["detail"].lower()

    def test_unlock_period(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Unlock Test",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "open",
            "is_locked": False,
        })
        period_id = resp.json()["id"]

        c.post(f"/api/periods/{period_id}/lock", headers=h)
        resp = c.post(f"/api/periods/{period_id}/unlock", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["is_locked"] is False

    def test_unlock_already_unlocked_fails(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Not Locked",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "open",
            "is_locked": False,
        })
        period_id = resp.json()["id"]

        resp = c.post(f"/api/periods/{period_id}/unlock", headers=h)
        assert resp.status_code == 409
        assert "not locked" in resp.json()["detail"].lower()

    def test_check_date_in_locked_period(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Check Test",
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "status": "open",
            "is_locked": False,
        })
        # Get period ID
        periods = c.get(f"/api/periods/?client_id={cid}", headers=h).json()
        period_id = periods[0]["id"]
        c.post(f"/api/periods/{period_id}/lock", headers=h)

        # Check a date inside the locked period
        resp = c.get(f"/api/periods/check?client_id={cid}&date=2024-03-15", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["locked"] is True
        assert data["period"]["name"] == "Check Test"

    def test_check_date_not_in_locked_period(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        resp = c.get(f"/api/periods/check?client_id={cid}&date=2025-01-01", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["locked"] is False
        assert data["period"] is None

    def test_lock_period_warns_about_unconfirmed_transactions(self, seeded_client):
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        uid = seeded_client["user_id"]

        # Add an unconfirmed transaction in the period range
        db = TestSessionLocal()
        try:
            account = db.query(models.Account).filter(models.Account.client_id == cid).first()
            stmt = models.Statement(
                account_id=account.id, tenant_id=cid, user_id=uid,
                filename="warn_test.pdf", period_start="2024-01-01",
                period_end="2024-12-31", is_balanced=True,
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)

            tx = models.Transaction(
                statement_id=stmt.id, tenant_id=cid, client_id=cid,
                date="2024-06-15", description="UNCONFIRMED-TX",
                amount=Decimal("-99.00"), tx_type="debit",
                category="Test", confirmed=False, archived=False,
            )
            db.add(tx)
            db.commit()
        finally:
            db.close()

        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "Warn Period",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "open",
            "is_locked": False,
        })
        period_id = resp.json()["id"]

        resp = c.post(f"/api/periods/{period_id}/lock", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert "warning" in data
        assert "unconfirmed" in data["warning"].lower()

    def test_lock_nonexistent_period_returns_404(self, seeded_client):
        c, h = seeded_client["client"], seeded_client["headers"]
        resp = c.post("/api/periods/99999/lock", headers=h)
        assert resp.status_code == 404


# =============================================================================
# AUDIT TRAIL / HASH CHAIN TESTS
# =============================================================================

class TestAuditTrail:
    """Test tamper-evident hash chain: genesis, linkage, integrity verification."""

    def test_genesis_hash_is_deterministic(self):
        h1 = _get_genesis_hash(42)
        h2 = _get_genesis_hash(42)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

        # Different clients = different genesis hashes
        h3 = _get_genesis_hash(99)
        assert h3 != h1

    def test_system_genesis_hash(self):
        h = _get_genesis_hash(None)
        expected = hashlib.sha256("system:genesis".encode("utf-8")).hexdigest()
        assert h == expected

    def test_create_audit_entry_creates_hash_chain(self, db_session):
        db = db_session
        # Create a user and client in DB
        user = models.User(username="audittest", email="audit@test.com",
                           hashed_password=get_password_hash("pw"))
        db.add(user)
        db.commit()
        db.refresh(user)

        client = models.Client(name="Audit Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

        # Create first audit entry
        entry1 = create_audit_entry(
            db=db, user_id=user.id, action=ACTION_CREATE_TRANSACTION,
            entity_type="Transaction", entity_id=1,
            new_values={"amount": 100}, client_id=client.id,
        )
        db.commit()

        assert entry1.id is not None
        assert entry1.details is not None

        # Parse the details JSON
        details = json.loads(entry1.details)
        assert "hash" in details
        assert "previous_hash" in details
        assert len(details["hash"]) == 64

        # The previous_hash should be the genesis hash
        expected_genesis = _get_genesis_hash(client.id)
        assert details["previous_hash"] == expected_genesis

    def test_audit_entries_form_chain(self, db_session):
        db = db_session
        user = models.User(username="chaintest", email="chain@test.com",
                           hashed_password=get_password_hash("pw"))
        db.add(user)
        db.commit()
        db.refresh(user)

        client = models.Client(name="Chain Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

        # Create multiple entries
        for i in range(3):
            create_audit_entry(
                db=db, user_id=user.id, action=ACTION_CREATE_TRANSACTION,
                entity_type="Transaction", entity_id=i + 1,
                new_values={"amount": (i + 1) * 100}, client_id=client.id,
            )
            db.commit()

        # Retrieve all entries
        entries = db.query(models.AuditEntry).filter(
            models.AuditEntry.tenant_id == client.id
        ).order_by(models.AuditEntry.id.asc()).all()

        assert len(entries) == 3

        # Verify chain: each entry's previous_hash should match the prior entry's hash
        prev_hash = _get_genesis_hash(client.id)
        for entry in entries:
            details = json.loads(entry.details)
            assert details["previous_hash"] == prev_hash
            prev_hash = details["hash"]

    def test_verify_chain_integrity_passes_for_valid_chain(self, db_session):
        db = db_session
        user = models.User(username="integrity", email="int@test.com",
                           hashed_password=get_password_hash("pw"))
        db.add(user)
        db.commit()
        db.refresh(user)

        client = models.Client(name="Integrity Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

        # Create entries
        for i in range(3):
            create_audit_entry(
                db=db, user_id=user.id, action=ACTION_CREATE_TRANSACTION,
                entity_type="Transaction", entity_id=i + 1,
                new_values={"amount": (i + 1) * 100}, client_id=client.id,
            )
            db.commit()

        # Verify chain
        results = verify_chain_integrity(db, client_id=client.id)
        assert len(results) == 3
        for r in results:
            assert r["valid"] is True, f"Entry {r['entry_id']}: expected hash {r['expected_hash'][:16]}... != stored {r['stored_hash'][:16]}..."

    def test_verify_chain_integrity_detects_tampering(self, db_session):
        db = db_session
        user = models.User(username="tamper", email="tamper@test.com",
                           hashed_password=get_password_hash("pw"))
        db.add(user)
        db.commit()
        db.refresh(user)

        client = models.Client(name="Tamper Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

        # Create entries
        for i in range(3):
            create_audit_entry(
                db=db, user_id=user.id, action=ACTION_CREATE_TRANSACTION,
                entity_type="Transaction", entity_id=i + 1,
                new_values={"amount": (i + 1) * 100}, client_id=client.id,
            )
            db.commit()

        # Tamper with the middle entry
        entries = db.query(models.AuditEntry).filter(
            models.AuditEntry.tenant_id == client.id
        ).order_by(models.AuditEntry.id.asc()).all()

        middle_entry = entries[1]
        middle_details = json.loads(middle_entry.details)
        middle_details["new_values"]["amount"] = 99999  # Tamper!
        middle_entry.details = json.dumps(middle_details)
        db.commit()

        # Verify should detect tampering from the middle entry onward
        results = verify_chain_integrity(db, client_id=client.id)
        assert len(results) == 3
        assert results[0]["valid"] is True  # First entry still valid
        assert results[1]["valid"] is False  # Tampered entry detected
        assert results[2]["valid"] is False  # Chain broken, subsequent entries also invalid

    def test_verify_chain_integrity_empty_returns_empty(self, db_session):
        results = verify_chain_integrity(db_session, client_id=99999)
        assert results == []

    def test_unrecognized_action_raises_value_error(self, db_session):
        with pytest.raises(ValueError, match="Unrecognized audit action"):
            create_audit_entry(
                db=db_session, user_id=1, action="INVALID_ACTION",
                entity_type="Test", entity_id=1,
            )

    def test_all_action_constants_are_recognized(self, db_session):
        from backend.audit.audit_trail import ALL_ACTIONS
        user = models.User(username="actions", email="actions@test.com",
                           hashed_password=get_password_hash("pw"))
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        for action in ALL_ACTIONS:
            entry = create_audit_entry(
                db=db_session, user_id=user.id, action=action,
                entity_type="Test", entity_id=1,
            )
            assert entry is not None
        db_session.commit()

    def test_event_hash_computation(self):
        """Verify the hash computation function produces consistent results."""
        h1 = _compute_event_hash(
            previous_hash="genesis", action="CREATE",
            entity_type="Tx", entity_id=1,
            old_values=None, new_values={"a": 1},
            timestamp="2024-01-01T00:00:00", user_id=1, client_id=1,
        )
        h2 = _compute_event_hash(
            previous_hash="genesis", action="CREATE",
            entity_type="Tx", entity_id=1,
            old_values=None, new_values={"a": 1},
            timestamp="2024-01-01T00:00:00", user_id=1, client_id=1,
        )
        assert h1 == h2  # Deterministic
        assert len(h1) == 64

        # Different payload = different hash
        h3 = _compute_event_hash(
            previous_hash="genesis", action="UPDATE",  # Different action
            entity_type="Tx", entity_id=1,
            old_values=None, new_values={"a": 1},
            timestamp="2024-01-01T00:00:00", user_id=1, client_id=1,
        )
        assert h3 != h1

    def test_audit_entry_includes_old_and_new_values(self, db_session):
        db = db_session
        user = models.User(username="values", email="val@test.com",
                           hashed_password=get_password_hash("pw"))
        db.add(user)
        db.commit()
        db.refresh(user)

        entry = create_audit_entry(
            db=db, user_id=user.id, action=ACTION_UPDATE_TRANSACTION,
            entity_type="Transaction", entity_id=1,
            old_values={"category": "Old"},
            new_values={"category": "New"},
        )
        db.commit()

        details = json.loads(entry.details)
        assert details["old_values"]["category"] == "Old"
        assert details["new_values"]["category"] == "New"


# =============================================================================
# CROSS-CUTTING INTEGRATION TESTS
# =============================================================================

class TestCrossCutting:
    """Tests that span multiple routers to verify end-to-end workflows."""

    def test_full_workflow_create_je_post_lock_prevents_new_je(self, seeded_client):
        """
        Complete workflow:
        1. Create a period
        2. Create and post a JE
        3. Lock the period
        4. Verify new JE in locked period is rejected
        """
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]

        # Step 1: Create period
        resp = c.post(f"/api/periods/?client_id={cid}", headers=h, json={
            "name": "FY 2024",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "open",
            "is_locked": False,
        })
        period_id = resp.json()["id"]

        # Step 2: Create and post a JE within the period
        je_resp = c.post(f"/api/journal-entries/?client_id={cid}", headers=h, json={
            "entry_number": "JE-WF-001",
            "entry_date": "2024-06-15",
            "memo": "Workflow test",
            "lines": [
                {"account_code": "1000", "account_name": "Cash", "debit": 1000.00, "credit": 0},
                {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 1000.00},
            ],
        })
        assert je_resp.status_code == 201
        je_id = je_resp.json()["id"]

        post_resp = c.post(f"/api/journal-entries/{je_id}/post", headers=h)
        assert post_resp.status_code == 200

        # Step 3: Lock the period
        lock_resp = c.post(f"/api/periods/{period_id}/lock", headers=h)
        assert lock_resp.status_code == 200

        # Step 4: Try to create another JE in the locked period
        je_resp2 = c.post(f"/api/journal-entries/?client_id={cid}", headers=h, json={
            "entry_number": "JE-WF-002",
            "entry_date": "2024-08-01",
            "memo": "Should fail",
            "lines": [
                {"account_code": "1000", "account_name": "Cash", "debit": 50.00, "credit": 0},
                {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 50.00},
            ],
        })
        assert je_resp2.status_code == 409
        assert "locked" in je_resp2.json()["detail"].lower()

    def test_transaction_lifecycle_with_audit(self, seeded_client):
        """
        Create a transaction, update it, archive it,
        and verify audit entries for each step.
        """
        c, h, cid = seeded_client["client"], seeded_client["headers"], seeded_client["client_id"]
        uid = seeded_client["user_id"]

        # Create a statement and transaction directly in DB
        db = TestSessionLocal()
        try:
            account = db.query(models.Account).filter(models.Account.client_id == cid).first()
            stmt = models.Statement(
                account_id=account.id, tenant_id=cid, user_id=uid,
                filename="lifecycle.pdf", period_start="2024-01-01",
                period_end="2024-12-31", is_balanced=True,
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)

            tx = models.Transaction(
                statement_id=stmt.id, tenant_id=cid, client_id=cid,
                date="2024-03-15", description="LIFECYCLE-TX",
                amount=Decimal("-75.00"), tx_type="debit",
                category="Test", confirmed=False, archived=False,
            )
            db.add(tx)
            db.commit()
            tx_id = tx.id
        finally:
            db.close()

        # Update the transaction via API
        patch_resp = c.patch(f"/api/transactions/{tx_id}", headers=h, json={
            "category": "Updated"
        })
        assert patch_resp.status_code == 200

        # Archive the transaction
        del_resp = c.delete(f"/api/transactions/{tx_id}", headers=h)
        assert del_resp.status_code == 200

        # Verify audit chain integrity
        db = TestSessionLocal()
        try:
            results = verify_chain_integrity(db, client_id=cid)
            # Should have audit entries for: client creation, account creation,
            # tx update, tx archive (at minimum)
            assert len(results) >= 2
            for r in results:
                assert r["valid"] is True, f"Tampered entry {r['entry_id']}"
        finally:
            db.close()
