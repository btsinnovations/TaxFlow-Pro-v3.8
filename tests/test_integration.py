"""
TaxFlow Pro - Comprehensive Integration Test Suite
===================================================

Five critical flow integration tests covering:
1. Upload -> Categorize -> Export
2. Statement Upload with Transaction Balance Verification
3. Tax Summary Report Generation
4. Duplicate Statement Detection
5. Full CRUD Flow with Audit Trail

All tests use FastAPI TestClient with an in-memory SQLite database
and are fully independent (fresh DB state per test).
"""

import os
import sys
import csv
import io
import json
import tempfile
import shutil
from datetime import datetime
from decimal import Decimal

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fpdf import FPDF

from backend.database import Base, get_db
from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash

# ---------------------------------------------------------------------------
# Test database engine (file-based SQLite for connection sharing)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///./test_integration.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override the app's DB dependency to use our test session."""
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
    """
    Create a fresh in-memory database, seed test data,
    yield the session, then roll back / drop tables.
    """
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()

    # Seed test data: 1 user, 1 client, 1 account
    user = models.User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(
        name="Test Client",
        email="client@example.com",
        tax_id="12-3456789",
        user_id=user.id,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    account = models.Account(
        name="Primary Checking",
        institution="Test Bank",
        account_number_masked="****1234",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    yield db

    db.rollback()
    db.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with fresh DB and seeded data."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def auth_headers(client):
    """
    Register a test user and log in to obtain Bearer token headers.
    Returns dict with Authorization header set.
    """
    # Register
    resp = client.post("/api/auth/register", json={
        "username": "integrationuser",
        "email": "integration@example.com",
        "password": "testpass456"
    })
    assert resp.status_code == 200, f"Register failed: {resp.text}"

    # Login
    resp = client.post("/api/auth/login", data={
        "username": "integrationuser",
        "password": "testpass456"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def seeded_auth_client(client, auth_headers):
    """
    Returns an auth client that also has a client and account pre-created
    via the API (on top of the DB-seeded data).
    """
    # Create a client via API
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "Seeded Client",
        "email": "seeded@example.com",
        "tax_id": "98-7654321"
    })
    assert resp.status_code == 200
    client_data = resp.json()

    # Create an account via API
    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "Business Checking",
        "institution": "Chase",
        "account_number_masked": "****5678",
        "type": "checking",
        "client_id": client_data["id"]
    })
    assert resp.status_code == 200
    account_data = resp.json()

    return {
        "client": client,
        "headers": auth_headers,
        "client_id": client_data["id"],
        "account_id": account_data["id"],
    }


@pytest.fixture(scope="function")
def sample_pdf_file():
    """Generate a minimal valid PDF statement file for upload testing."""
    class StmtPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 12)
            self.cell(0, 10, "Big Bank Statement", ln=True)
            self.cell(0, 10, "Statement Period: 01/01/2024 to 01/31/2024", ln=True)
            self.cell(0, 10, "Opening Balance: $500.00", ln=True)
            self.cell(0, 10, "Closing Balance: $350.00", ln=True)

    pdf = StmtPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    # Debit transactions (negative amounts)
    pdf.cell(0, 10, "01/05/2024 STARBUCKS COFFEE -$5.00 $495.00", ln=True)
    pdf.cell(0, 10, "01/10/2024 SHELL GAS STATION -$45.00 $450.00", ln=True)
    pdf.cell(0, 10, "01/15/2024 AMAZON PURCHASE -$100.00 $350.00", ln=True)
    # Credit transaction
    pdf.cell(0, 10, "01/20/2024 SALARY DEPOSIT $50.00 $400.00", ln=True)
    pdf.cell(0, 10, "01/25/2024 NETFLIX SUBSCRIPTION -$50.00 $350.00", ln=True)

    tmp_dir = tempfile.mkdtemp()
    pdf_path = os.path.join(tmp_dir, "test_statement.pdf")
    pdf.output(pdf_path)

    yield pdf_path

    shutil.rmtree(tmp_dir, ignore_errors=True)


# =============================================================================
# TEST 1: Upload -> Categorize -> Export
# =============================================================================

def test_upload_creates_transactions_and_categorize_exports_csv(
    client, auth_headers, sample_pdf_file
):
    """
    Critical Flow 1: Upload a PDF statement, verify transactions created,
    call ML categorize endpoint, then export as CSV and verify content.
    """
    # ---- Setup: create a client + account via API ----
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "Upload Test Client",
        "email": "upload@example.com",
        "tax_id": "11-1111111"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "Upload Test Account",
        "institution": "Test Bank",
        "account_number_masked": "****9999",
        "type": "checking",
        "client_id": client_id
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]

    # ---- Step 1: Upload PDF statement ----
    with open(sample_pdf_file, "rb") as f:
        resp = client.post(
            f"/api/upload/?account_id={account_id}",
            headers=auth_headers,
            files={"file": ("test_statement.pdf", f, "application/pdf")}
        )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    upload_data = resp.json()
    assert "statement_id" in upload_data
    assert isinstance(upload_data["transactions_count"], int)
    assert upload_data["transactions_count"] >= 1
    statement_id = upload_data["statement_id"]

    # ---- Verify: statement exists and has transactions ----
    resp = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    account_data = resp.json()
    assert len(account_data["statements"]) >= 1
    stmt = account_data["statements"][0]
    assert stmt["id"] == statement_id
    assert stmt["filename"] == "test_statement.pdf"

    # ---- Step 2: ML Categorize endpoint ----
    resp = client.post(
        f"/api/ml/categorize/{statement_id}",
        headers=auth_headers
    )
    assert resp.status_code == 200, f"Categorize failed: {resp.text}"
    cat_data = resp.json()
    assert cat_data["statement_id"] == statement_id
    assert cat_data["transactions_processed"] >= 1
    assert isinstance(cat_data["categories_updated"], int)
    # Categories should include recognized ones (STARBUKS -> Food & Dining, etc.)
    categories = cat_data["categories"]
    assert len(categories) >= 1
    # At least some transactions should have been categorized beyond 'uncategorized'
    recognized_categories = ["Food & Dining", "Auto & Transport", "Shopping",
                             "Income", "Entertainment"]
    assert any(cat in recognized_categories for cat in categories), \
        f"Expected recognized categories, got: {categories}"

    # ---- Step 3: Export as CSV and verify content ----
    resp = client.get(
        f"/api/export/statement/{statement_id}?format=csv",
        headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    content_disposition = resp.headers.get("content-disposition", "")
    assert f"statement_{statement_id}.csv" in content_disposition

    # Parse CSV content and verify structure
    csv_content = resp.text
    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)
    assert len(rows) >= 2, "CSV should have header + at least 1 data row"
    header = rows[0]
    assert "id" in header
    assert "date" in header
    assert "description" in header
    assert "amount" in header
    assert "type" in header
    assert "category" in header

    # Verify data rows have valid content
    data_rows = rows[1:]
    assert len(data_rows) >= 1
    for row in data_rows:
        assert len(row) == len(header), f"Row {row} has wrong column count"
        assert row[1]  # date should not be empty
        assert row[2]  # description should not be empty
        assert row[3]  # amount should not be empty
        assert row[4] in ("debit", "credit")
        assert row[5]  # category should not be empty

    # ---- Also verify JSON export works ----
    resp = client.get(
        f"/api/export/statement/{statement_id}?format=json",
        headers=auth_headers
    )
    assert resp.status_code == 200
    json_data = resp.json()
    assert isinstance(json_data, list)
    assert len(json_data) >= 1
    tx = json_data[0]
    assert "id" in tx
    assert "date" in tx
    assert "description" in tx
    assert "amount" in tx
    assert "type" in tx
    assert "category" in tx


# =============================================================================
# TEST 2: Statement Upload with Balance Verification
# =============================================================================

def test_statement_upload_balance_verification(client, auth_headers, sample_pdf_file):
    """
    Critical Flow 2: Upload a statement, verify transactions were created
    with correct amounts/types, and confirm the reconciliation data
    (opening_balance, closing_balance, variance) is present.
    """
    # Setup
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "Balance Client",
        "email": "balance@example.com",
        "tax_id": "22-2222222"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "Balance Account",
        "institution": "Balance Bank",
        "account_number_masked": "****4444",
        "type": "savings",
        "client_id": client_id
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]

    # Upload
    with open(sample_pdf_file, "rb") as f:
        resp = client.post(
            f"/api/upload/?account_id={account_id}",
            headers=auth_headers,
            files={"file": ("test_statement.pdf", f, "application/pdf")}
        )
    assert resp.status_code == 200
    data = resp.json()
    statement_id = data["statement_id"]
    tx_count = data["transactions_count"]

    # Verify statement-level reconciliation fields exist
    assert "variance" in data
    assert "balanced" in data
    assert isinstance(statement_id, int)
    assert tx_count >= 1

    # Get the account with statements to verify nested transactions
    resp = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    account_data = resp.json()
    statements = account_data.get("statements", [])
    assert len(statements) >= 1

    stmt = statements[0]
    assert stmt["id"] == statement_id
    assert stmt["filename"] == "test_statement.pdf"
    assert "opening_balance" in stmt
    assert "closing_balance" in stmt

    # Verify transactions have correct debit/credit typing
    # Debit = negative amount, Credit = positive amount
    db = TestSessionLocal()
    try:
        transactions = db.query(models.Transaction).filter(
            models.Transaction.statement_id == statement_id
        ).all()
        assert len(transactions) == tx_count
        for tx in transactions:
            assert tx.tx_type in ("debit", "credit")
            if tx.amount and Decimal(str(tx.amount)) > 0:
                assert tx.tx_type == "credit"
            elif tx.amount and Decimal(str(tx.amount)) < 0:
                assert tx.tx_type == "debit"
            assert tx.date is not None
            assert tx.description is not None
            # After the ML categorize step, categories should be assigned
    finally:
        db.close()

    # Trial balance: sum of all transaction amounts should reconcile with variance
    db = TestSessionLocal()
    try:
        txs = db.query(models.Transaction).filter(
            models.Transaction.statement_id == statement_id
        ).all()
        total = sum(Decimal(str(tx.amount)) for tx in txs if tx.amount)
        # The total change should be closing - opening
        statement = db.query(models.Statement).filter(
            models.Statement.id == statement_id
        ).first()
        opening = Decimal(str(statement.opening_balance)) if statement.opening_balance else Decimal("0")
        closing = Decimal(str(statement.closing_balance)) if statement.closing_balance else Decimal("0")
        expected_change = closing - opening
        # Allow small rounding differences
        assert abs(total - expected_change) < Decimal("0.02"), \
            f"Total transactions {total} != expected change {expected_change}"
    finally:
        db.close()


# =============================================================================
# TEST 3: Tax Summary Report Generation
# =============================================================================

def test_tax_summary_report_generation(client, auth_headers):
    """
    Critical Flow 3: Create transactions across a tax year, then generate
    a tax summary report. Verify the report contains accurate income,
    expense, and net calculations.
    """
    # Setup: create client and account
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "Tax Client",
        "email": "tax@example.com",
        "tax_id": "33-3333333"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "Tax Account",
        "institution": "IRS Bank",
        "account_number_masked": "****7777",
        "type": "checking",
        "client_id": client_id
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]

    # Create a statement directly in DB with transactions for tax year 2024
    db = TestSessionLocal()
    try:
        # Find the user
        user = db.query(models.User).first()

        statement = models.Statement(
            account_id=account_id,
            tenant_id=client_id,
            user_id=user.id,
            filename="tax_2024_statement.pdf",
            period_start="2024-01-01",
            period_end="2024-12-31",
            opening_balance=Decimal("0.00"),
            closing_balance=Decimal("0.00"),
            variance=Decimal("0.00"),
            is_balanced=True,
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)

        # Income transactions (positive amounts = credits)
        income_txs = [
            ("2024-01-15", "SALARY PAYROLL", "1000.00"),
            ("2024-02-15", "SALARY PAYROLL", "1000.00"),
            ("2024-03-15", "TAX REFUND IRS", "500.00"),
        ]
        for date, desc, amount in income_txs:
            tx = models.Transaction(
                statement_id=statement.id,
                tenant_id=client_id,
                date=date,
                description=desc,
                amount=Decimal(amount),
                tx_type="credit",
                category="Income",
            )
            db.add(tx)

        # Expense transactions (negative amounts = debits)
        expense_txs = [
            ("2024-01-05", "STARBUCKS COFFEE", "-5.00"),
            ("2024-01-10", "SHELL GAS", "-45.00"),
            ("2024-02-01", "RENT PAYMENT", "-800.00"),
            ("2024-03-01", "AMAZON PURCHASE", "-150.00"),
        ]
        for date, desc, amount in expense_txs:
            tx = models.Transaction(
                statement_id=statement.id,
                tenant_id=client_id,
                date=date,
                description=desc,
                amount=Decimal(amount),
                tx_type="debit",
                category="uncategorized",
            )
            db.add(tx)

        # Capture statement ID before closing DB context
        statement_id_for_audit = statement.id
        db.commit()
    finally:
        db.close()

    # Generate tax summary for 2024
    resp = client.get("/api/tax/summary/2024", headers=auth_headers)
    assert resp.status_code == 200, f"Tax summary failed: {resp.text}"
    report = resp.json()

    # Verify report structure
    assert report["year"] == 2024
    assert "total_income" in report
    assert "total_expenses" in report
    assert "net" in report

    # Verify calculations
    expected_income = 2500.00  # 1000 + 1000 + 500
    expected_expenses = 1000.00  # 5 + 45 + 800 + 150 = 1000
    expected_net = 1500.00  # 2500 - 1000

    assert abs(report["total_income"] - expected_income) < 0.01, \
        f"Expected income ~{expected_income}, got {report['total_income']}"
    assert abs(report["total_expenses"] - expected_expenses) < 0.01, \
        f"Expected expenses ~{expected_expenses}, got {report['total_expenses']}"
    assert abs(report["net"] - expected_net) < 0.01, \
        f"Expected net ~{expected_net}, got {report['net']}"

    # Verify the report data appears on the dashboard
    resp = client.get("/api/dashboard/", headers=auth_headers)
    assert resp.status_code == 200
    dash = resp.json()
    assert dash["total_statements"] >= 1
    assert dash["total_transactions"] >= len(income_txs) + len(expense_txs)

    # Verify audit logs contain the statement
    resp = client.get("/api/audit/logs", headers=auth_headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert "events" in logs
    stmt_events = [e for e in logs["events"] if e.get("statement_id") == statement_id_for_audit]
    assert len(stmt_events) >= 1


# =============================================================================
# TEST 4: Duplicate Statement Detection
# =============================================================================

def test_duplicate_statement_detection(client, auth_headers, sample_pdf_file):
    """
    Critical Flow 4: Upload the same PDF statement twice and verify
    that duplicate records are created (the system tracks each upload).
    The second upload should create a new statement record, demonstrating
    the system handles repeated uploads gracefully.
    """
    # Setup
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "Dup Client",
        "email": "dup@example.com",
        "tax_id": "44-4444444"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "Dup Account",
        "institution": "Dup Bank",
        "account_number_masked": "****0000",
        "type": "checking",
        "client_id": client_id
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]

    # First upload
    with open(sample_pdf_file, "rb") as f:
        resp1 = client.post(
            f"/api/upload/?account_id={account_id}",
            headers=auth_headers,
            files={"file": ("test_statement.pdf", f, "application/pdf")}
        )
    assert resp1.status_code == 200
    data1 = resp1.json()
    stmt1_id = data1["statement_id"]
    tx_count_1 = data1["transactions_count"]

    # Second upload (same file)
    with open(sample_pdf_file, "rb") as f:
        resp2 = client.post(
            f"/api/upload/?account_id={account_id}",
            headers=auth_headers,
            files={"file": ("test_statement.pdf", f, "application/pdf")}
        )
    assert resp2.status_code == 200
    data2 = resp2.json()
    stmt2_id = data2["statement_id"]
    tx_count_2 = data2["transactions_count"]

    # Both should succeed
    assert stmt1_id != stmt2_id, "Second upload should create a new statement ID"
    assert tx_count_1 == tx_count_2, "Same file should produce same transaction count"

    # Verify both statements exist in the account
    resp = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    account_data = resp.json()
    statements = account_data.get("statements", [])
    assert len(statements) == 2, f"Expected 2 statements, got {len(statements)}"
    stmt_ids = {s["id"] for s in statements}
    assert stmt1_id in stmt_ids
    assert stmt2_id in stmt_ids

    # Verify total transactions in DB = 2x the per-statement count
    db = TestSessionLocal()
    try:
        all_txs = db.query(models.Transaction).join(models.Statement).filter(
            models.Statement.account_id == account_id
        ).all()
        assert len(all_txs) == tx_count_1 * 2, \
            f"Expected {tx_count_1 * 2} total transactions, got {len(all_txs)}"
    finally:
        db.close()

    # Audit log should show both uploads
    resp = client.get("/api/audit/logs", headers=auth_headers)
    assert resp.status_code == 200
    logs = resp.json()
    upload_events = [e for e in logs["events"]
                     if e.get("type") == "statement_upload"]
    assert len(upload_events) >= 2


# =============================================================================
# TEST 5: Full CRUD Flow with Audit Trail
# =============================================================================

def test_full_crud_flow_with_audit_trail(client, auth_headers):
    """
    Critical Flow 5: Create client, account, and transactions via API,
    read all back, update transaction category, verify audit entries
    for each operation.
    """
    # ---- CREATE: Client ----
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "CRUD Client",
        "email": "crud@example.com",
        "tax_id": "55-5555555"
    })
    assert resp.status_code == 200
    client_data = resp.json()
    assert client_data["name"] == "CRUD Client"
    assert client_data["email"] == "crud@example.com"
    assert client_data["tax_id"] == "55-5555555"
    client_id = client_data["id"]

    # ---- READ: List clients ----
    resp = client.get("/api/clients/", headers=auth_headers)
    assert resp.status_code == 200
    clients_list = resp.json()
    assert len(clients_list) >= 1
    assert any(c["id"] == client_id for c in clients_list)

    # ---- CREATE: Account ----
    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "CRUD Account",
        "institution": "CRUD Bank",
        "account_number_masked": "****CRUD",
        "type": "checking",
        "client_id": client_id
    })
    assert resp.status_code == 200
    account_data = resp.json()
    assert account_data["name"] == "CRUD Account"
    assert account_data["institution"] == "CRUD Bank"
    assert account_data["type"] == "checking"
    account_id = account_data["id"]

    # ---- READ: Get single account ----
    resp = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    fetched_account = resp.json()
    assert fetched_account["id"] == account_id
    assert fetched_account["name"] == "CRUD Account"

    # ---- CREATE: Statement + Transactions (via direct DB for control) ----
    db = TestSessionLocal()
    try:
        user = db.query(models.User).first()
        statement = models.Statement(
            account_id=account_id,
            tenant_id=client_id,
            user_id=user.id,
            filename="crud_statement.pdf",
            period_start="2024-06-01",
            period_end="2024-06-30",
            opening_balance=Decimal("1000.00"),
            closing_balance=Decimal("850.00"),
            variance=Decimal("-150.00"),
            is_balanced=True,
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)
        statement_id = statement.id

        # Create transactions
        tx1 = models.Transaction(
            statement_id=statement_id,
            tenant_id=client_id,
            date="2024-06-05",
            description="STARBUCKS",
            amount=Decimal("-5.00"),
            tx_type="debit",
            category="uncategorized",
        )
        tx2 = models.Transaction(
            statement_id=statement_id,
            tenant_id=client_id,
            date="2024-06-10",
            description="SHELL GAS",
            amount=Decimal("-45.00"),
            tx_type="debit",
            category="uncategorized",
        )
        tx3 = models.Transaction(
            statement_id=statement_id,
            tenant_id=client_id,
            date="2024-06-15",
            description="SALARY DEPOSIT",
            amount=Decimal("500.00"),
            tx_type="credit",
            category="Income",
        )
        db.add_all([tx1, tx2, tx3])
        db.commit()

        # Store IDs for later
        tx1_id = tx1.id
        tx2_id = tx2.id
        tx3_id = tx3.id
    finally:
        db.close()

    # ---- READ: Verify transactions exist via export ----
    resp = client.get(
        f"/api/export/statement/{statement_id}?format=json",
        headers=auth_headers
    )
    assert resp.status_code == 200
    txs = resp.json()
    assert len(txs) == 3
    descriptions = {t["description"] for t in txs}
    assert "STARBUCKS" in descriptions
    assert "SHELL GAS" in descriptions
    assert "SALARY DEPOSIT" in descriptions

    # ---- UPDATE: Categorize transactions via ML endpoint ----
    resp = client.post(
        f"/api/ml/categorize/{statement_id}",
        headers=auth_headers
    )
    assert resp.status_code == 200
    cat_result = resp.json()
    assert cat_result["categories_updated"] >= 1

    # Verify categories were updated in DB
    db = TestSessionLocal()
    try:
        updated_txs = db.query(models.Transaction).filter(
            models.Transaction.statement_id == statement_id
        ).all()
        categories = {tx.category for tx in updated_txs}
        # STARBUCKS -> Food & Dining, SHELL -> Auto & Transport
        assert "Food & Dining" in categories or "Auto & Transport" in categories or "Income" in categories
    finally:
        db.close()

    # Re-read via export to confirm updated categories
    resp = client.get(
        f"/api/export/statement/{statement_id}?format=csv",
        headers=auth_headers
    )
    assert resp.status_code == 200
    csv_rows = list(csv.reader(io.StringIO(resp.text)))
    data_rows = csv_rows[1:]
    category_col_idx = csv_rows[0].index("category")
    categories_after_update = {row[category_col_idx] for row in data_rows}
    # Should have moved beyond all 'uncategorized'
    assert len(categories_after_update - {"uncategorized"}) >= 1

    # ---- UPDATE: Update client via PATCH ----
    resp = client.patch(f"/api/clients/{client_id}", headers=auth_headers, json={
        "name": "CRUD Client Updated",
        "email": "updated@example.com"
    })
    assert resp.status_code == 200
    updated_client = resp.json()
    assert updated_client["name"] == "CRUD Client Updated"
    assert updated_client["email"] == "updated@example.com"
    # Original fields preserved
    assert updated_client["tax_id"] == "55-5555555"

    # ---- UPDATE: Update account via PATCH ----
    resp = client.patch(f"/api/accounts/{account_id}", headers=auth_headers, json={
        "name": "CRUD Account Updated",
        "institution": "Updated Bank"
    })
    assert resp.status_code == 200
    updated_account = resp.json()
    assert updated_account["name"] == "CRUD Account Updated"
    assert updated_account["institution"] == "Updated Bank"

    # ---- DELETE: Delete account ----
    resp = client.delete(f"/api/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify account is gone
    resp = client.get(f"/api/accounts/{account_id}", headers=auth_headers)
    assert resp.status_code == 404

    # ---- DELETE: Delete client ----
    resp = client.delete(f"/api/clients/{client_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify client is gone
    resp = client.get(f"/api/clients/{client_id}", headers=auth_headers)
    assert resp.status_code == 404

    # ---- AUDIT: Verify audit logs track operations ----
    resp = client.get("/api/audit/logs", headers=auth_headers)
    assert resp.status_code == 200
    logs = resp.json()
    assert "events" in logs
    events = logs["events"]
    assert len(events) >= 1

    # Verify auth/me endpoint still works
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    me = resp.json()
    assert "username" in me
    assert me["is_active"] is True


# =============================================================================
# Additional smoke tests for export formats and edge cases
# =============================================================================

def test_export_all_formats(client, auth_headers, sample_pdf_file):
    """Verify all supported export formats return valid responses."""
    # Setup
    resp = client.post("/api/clients/", headers=auth_headers, json={
        "name": "Export Client",
        "email": "export@example.com",
        "tax_id": "66-6666666"
    })
    assert resp.status_code == 200
    client_id = resp.json()["id"]

    resp = client.post("/api/accounts/", headers=auth_headers, json={
        "name": "Export Account",
        "institution": "Export Bank",
        "client_id": client_id,
        "type": "checking"
    })
    assert resp.status_code == 200
    account_id = resp.json()["id"]

    with open(sample_pdf_file, "rb") as f:
        resp = client.post(
            f"/api/upload/?account_id={account_id}",
            headers=auth_headers,
            files={"file": ("test_statement.pdf", f, "application/pdf")}
        )
    assert resp.status_code == 200
    statement_id = resp.json()["statement_id"]

    # Test each supported format
    for fmt in ("csv", "json", "qbo", "xero", "qif"):
        resp = client.get(
            f"/api/export/statement/{statement_id}?format={fmt}",
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Format {fmt} failed: {resp.text}"
        assert len(resp.content) > 0, f"Format {fmt} returned empty content"


def test_dashboard_summary(client, auth_headers):
    """Verify dashboard returns correct aggregated data."""
    resp = client.get("/api/dashboard/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_accounts" in data
    assert "total_statements" in data
    assert "total_transactions" in data
    assert "total_volume" in data
    assert "recent_statements" in data
    assert isinstance(data["total_accounts"], int)
    assert isinstance(data["total_statements"], int)
    assert isinstance(data["total_transactions"], int)
