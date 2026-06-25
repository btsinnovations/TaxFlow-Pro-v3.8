"""Tests for the Chart of Accounts v3.11 module.

These tests use the existing GLAccount table so v3.10 data stays compatible.
Each test receives a fresh in-memory SQLite database via the shared harness.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import AccountType, create_account, delete_account, get_accounts, update_account
from datetime import date


def _seed_tenant_and_user(db: Session):
    """Create a minimal user + client pair and return (user, tenant_id)."""
    user = models.User(
        username="coauser",
        email="coa@example.com",
        hashed_password="$2b$12$dummy.dummy.dummy.dummy.dummy",
        is_active=True,
        encryption_salt="c2FsdHN0cmluZw==",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="COA Tenant", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return user, client.id


def test_account_type_enum_values():
    """AccountType exposes the five canonical bookkeeping classes."""
    values = {m.value for m in AccountType}
    assert values == {"asset", "liability", "equity", "income", "expense"}


def test_get_accounts_empty(db):
    user, tenant_id = _seed_tenant_and_user(db)
    assert get_accounts(db, tenant_id=tenant_id, user_id=user.id) == []


def test_create_and_list_account(db):
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash in Bank",
        account_type="asset",
    )
    assert created["number"] == "1000"
    assert created["name"] == "Cash in Bank"
    assert created["type"] == "asset"
    assert created["balance"] is None

    accounts = get_accounts(db, tenant_id=tenant_id, user_id=user.id)
    assert len(accounts) == 1
    assert accounts[0]["number"] == "1000"


def test_create_account_rejects_duplicate_code(db):
    user, tenant_id = _seed_tenant_and_user(db)
    create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="2000",
        name="Credit Card",
        account_type="liability",
    )
    with pytest.raises(Exception) as exc_info:
        create_account(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            code="2000",
            name="Duplicate",
            account_type="liability",
        )
    assert "Account code already exists" in str(exc_info.value)


def test_update_account(db):
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="3000",
        name="Owner Equity",
        account_type="equity",
    )
    updated = update_account(
        db=db,
        account_id=created["id"],
        tenant_id=tenant_id,
        user_id=user.id,
        name="Owner's Capital",
    )
    assert updated["name"] == "Owner's Capital"
    assert updated["type"] == "equity"


def test_update_account_rejects_self_parent(db):
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="4000",
        name="Revenue",
        account_type="income",
    )
    with pytest.raises(Exception) as exc_info:
        update_account(
            db=db,
            account_id=created["id"],
            tenant_id=tenant_id,
            user_id=user.id,
            parent_id=created["id"],
        )
    assert "cannot be its own parent" in str(exc_info.value)


def test_delete_account(db):
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="5000",
        name="Office Supplies",
        account_type="expense",
    )
    delete_account(
        db=db,
        account_id=created["id"],
        tenant_id=tenant_id,
        user_id=user.id,
    )
    assert get_accounts(db, tenant_id=tenant_id, user_id=user.id) == []


def test_delete_account_referenced_by_transaction(db):
    user, tenant_id = _seed_tenant_and_user(db)
    account = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="6000",
        name="Groceries",
        account_type="expense",
    )

    # Minimal account + statement required to satisfy FKs on Transaction.
    bank_account = models.Account(
        name="Checking",
        client_id=tenant_id,
        tenant_id=tenant_id,
        user_id=user.id,
        type="checking",
    )
    db.add(bank_account)
    db.commit()
    db.refresh(bank_account)

    statement = models.Statement(
        account_id=bank_account.id,
        tenant_id=tenant_id,
        user_id=user.id,
        filename="stmt.pdf",
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    txn = models.Transaction(
        statement_id=statement.id,
        tenant_id=tenant_id,
        user_id=user.id,
        gl_account_id=account["id"],
        description="Store",
        amount=12.50,
    )
    db.add(txn)
    db.commit()

    with pytest.raises(Exception) as exc_info:
        delete_account(
            db=db,
            account_id=account["id"],
            tenant_id=tenant_id,
            user_id=user.id,
        )
    assert "referenced by transactions" in str(exc_info.value)


def test_delete_account_referenced_by_ledger_entry(db):
    user, tenant_id = _seed_tenant_and_user(db)
    asset = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1100",
        name="Equipment",
        account_type="asset",
    )
    expense = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="5100",
        name="Depreciation",
        account_type="expense",
    )
    entry = models.GeneralLedgerEntry(
        tenant_id=tenant_id,
        user_id=user.id,
        date=date(2026, 1, 31),
        description="Monthly depreciation",
        debit_account_id=expense["id"],
        credit_account_id=asset["id"],
        amount=50.00,
    )
    db.add(entry)
    db.commit()

    with pytest.raises(Exception) as exc_info:
        delete_account(
            db=db,
            account_id=asset["id"],
            tenant_id=tenant_id,
            user_id=user.id,
        )
    assert "referenced by general ledger entries" in str(exc_info.value)


def test_delete_account_referenced_by_categorization_rule(db):
    user, tenant_id = _seed_tenant_and_user(db)
    account = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="6100",
        name="Advertising",
        account_type="expense",
    )
    rule = models.CategorizationRule(
        tenant_id=tenant_id,
        user_id=user.id,
        name="Ad spend",
        pattern="GOOGLE ADS",
        gl_account_id=account["id"],
    )
    db.add(rule)
    db.commit()

    with pytest.raises(Exception) as exc_info:
        delete_account(
            db=db,
            account_id=account["id"],
            tenant_id=tenant_id,
            user_id=user.id,
        )
    assert "referenced by categorization rules" in str(exc_info.value)


def test_api_coa_crud(auth_client: TestClient):
    """End-to-end CRUD through the FastAPI router."""
    c = auth_client

    # Create tenant via client endpoint.
    resp = c.post("/api/clients/", json={"name": "COA API Client"})
    assert resp.status_code == 200
    tenant_id = resp.json()["id"]

    # POST
    resp = c.post("/api/coa", json={
        "number": "1010",
        "name": "Operating Checking",
        "type": "asset",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["number"] == "1010"
    account_id = data["id"]

    # GET
    resp = c.get("/api/coa")
    assert resp.status_code == 200
    items = resp.json()
    assert any(item["id"] == account_id for item in items)

    # PUT
    resp = c.put(f"/api/coa/{account_id}", json={"name": "Operating Checking Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Operating Checking Updated"

    # DELETE
    resp = c.delete(f"/api/coa/{account_id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = c.get("/api/coa")
    assert not any(item["id"] == account_id for item in resp.json())


def test_api_coa_rejects_transaction_referenced_delete(auth_client: TestClient):
    c = auth_client
    resp = c.post("/api/clients/", json={"name": "Guard Client"})
    assert resp.status_code == 200
    tenant_id = resp.json()["id"]

    resp = c.post("/api/coa", json={
        "number": "7000",
        "name": "Meals",
        "type": "expense",
    })
    assert resp.status_code == 201
    coa_id = resp.json()["id"]

    # Need a bank account + statement to create a transaction.
    resp = c.post("/api/accounts/", json={
        "name": "Checking",
        "client_id": tenant_id,
        "type": "checking",
    })
    assert resp.status_code == 200
    bank_account_id = resp.json()["id"]

    resp = c.post("/api/upload/", files={
        "file": ("stmt.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")
    }, data={"client_id": str(tenant_id)})
    # Upload may fail parser, but we only need a statement row.  Fall back to direct DB seeding
    # for the guard test so parser state does not matter.
    from backend.tests.conftest import override_get_db

    db_gen = override_get_db()
    db = next(db_gen)
    try:
        statement = db.query(models.Statement).filter(
            models.Statement.account_id == bank_account_id
        ).first()
        if statement is None:
            statement = models.Statement(
                account_id=bank_account_id,
                tenant_id=tenant_id,
                user_id=resp.json()["user_id"] if resp.status_code == 200 else 1,
                filename="stmt.pdf",
            )
            db.add(statement)
            db.commit()
            db.refresh(statement)

        txn = models.Transaction(
            statement_id=statement.id,
            tenant_id=tenant_id,
            user_id=statement.user_id,
            gl_account_id=coa_id,
            description="Lunch",
            amount=25.00,
        )
        db.add(txn)
        db.commit()
    finally:
        db.close()
        try:
            next(db_gen)
        except StopIteration:
            pass

    resp = c.delete(f"/api/coa/{coa_id}")
    assert resp.status_code == 409
    assert "transactions" in resp.json()["detail"]


def test_api_coa_requires_auth(client: TestClient):
    resp = client.get("/api/coa")
    assert resp.status_code == 401
