"""Tests for the Chart of Accounts v3.11.6 module.

Tests use the new ``coa_accounts`` table introduced in v3.11.6.
Each test receives a fresh in-memory SQLite database via the shared harness.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import (
    AccountType,
    create_account,
    delete_account,
    get_accounts,
    get_account,
    update_account,
    seed_standard_coa,
    renumber_account,
    reassign_parent,
)
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


def _seed_tenant_and_user_b(db: Session):
    """Create a second tenant/user pair for isolation tests."""
    user = models.User(
        username="coauser_b",
        email="coa_b@example.com",
        hashed_password="$2b$12$dummy.dummy.dummy.dummy.dummy",
        is_active=True,
        encryption_salt="c2FsdHN0cmluZw==",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    client = models.Client(name="COA Tenant B", user_id=user.id)
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


def test_create_account_rejects_non_integer_code(db):
    user, tenant_id = _seed_tenant_and_user(db)
    with pytest.raises(Exception) as exc_info:
        create_account(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            code="ABC",
            name="Bad Account",
            account_type="asset",
        )
    assert "must be an integer" in str(exc_info.value)


def test_create_account_rejects_out_of_range_number(db):
    user, tenant_id = _seed_tenant_and_user(db)
    with pytest.raises(Exception) as exc_info:
        create_account(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            code="999",
            name="Too Low for Asset",
            account_type="asset",
        )
    assert "outside the asset range" in str(exc_info.value)


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
        coa_account_id=account["id"],
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
        debit_coa_account_id=expense["id"],
        credit_coa_account_id=asset["id"],
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
    # CategorizationRule requires a non-null gl_account_id FK.
    # Create a minimal GLAccount row to satisfy the constraint.
    gl_acct = models.GLAccount(
        tenant_id=tenant_id,
        user_id=user.id,
        code="6100",
        name="Advertising GL",
        account_type="expense",
    )
    db.add(gl_acct)
    db.commit()
    db.refresh(gl_acct)

    rule = models.CategorizationRule(
        tenant_id=tenant_id,
        user_id=user.id,
        name="Ad spend",
        pattern="GOOGLE ADS",
        gl_account_id=gl_acct.id,
        coa_account_id=account["id"],
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


def test_delete_account_with_child_blocked(db):
    """Cannot delete an account that has child accounts."""
    user, tenant_id = _seed_tenant_and_user(db)
    parent = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    child = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1010",
        name="Operating Checking",
        account_type="asset",
        parent_id=parent["id"],
    )
    with pytest.raises(Exception) as exc_info:
        delete_account(
            db=db,
            account_id=parent["id"],
            tenant_id=tenant_id,
            user_id=user.id,
        )
    assert "child accounts" in str(exc_info.value)


def test_seed_standard_coa(db):
    """Seed a standard COA for a new tenant."""
    user, tenant_id = _seed_tenant_and_user(db)
    accounts = seed_standard_coa(db, tenant_id=tenant_id, user_id=user.id)
    assert len(accounts) > 10
    # Check we have all five types
    types = {a["type"] for a in accounts}
    assert "asset" in types
    assert "liability" in types
    assert "equity" in types
    assert "income" in types
    assert "expense" in types
    # Check numbers are in correct ranges
    for a in accounts:
        num = int(a["number"])
        if a["type"] == "asset":
            assert 1000 <= num <= 1999
        elif a["type"] == "liability":
            assert 2000 <= num <= 2999
        elif a["type"] == "equity":
            assert 3000 <= num <= 3999
        elif a["type"] == "income":
            assert 4000 <= num <= 4999
        elif a["type"] == "expense":
            assert 5000 <= num <= 9999


def test_seed_standard_coa_rejects_double_seed(db):
    """Cannot seed COA twice for the same tenant."""
    user, tenant_id = _seed_tenant_and_user(db)
    seed_standard_coa(db, tenant_id=tenant_id, user_id=user.id)
    with pytest.raises(Exception) as exc_info:
        seed_standard_coa(db, tenant_id=tenant_id, user_id=user.id)
    assert "already seeded" in str(exc_info.value)


def test_renumber_account(db):
    """Renumber an existing account within its type range."""
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    renumbered = renumber_account(
        db=db,
        account_id=created["id"],
        tenant_id=tenant_id,
        new_number=1050,
    )
    assert renumbered["number"] == "1050"


def test_renumber_account_rejects_out_of_range(db):
    """Renumber rejects numbers outside the account's type range."""
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    with pytest.raises(Exception) as exc_info:
        renumber_account(
            db=db,
            account_id=created["id"],
            tenant_id=tenant_id,
            new_number=5000,  # expense range, not asset
        )
    assert "outside" in str(exc_info.value) and "asset range" in str(exc_info.value)


def test_renumber_account_rejects_duplicate(db):
    """Renumber rejects numbers already in use."""
    user, tenant_id = _seed_tenant_and_user(db)
    create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    second = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1010",
        name="Checking",
        account_type="asset",
    )
    with pytest.raises(Exception) as exc_info:
        renumber_account(
            db=db,
            account_id=second["id"],
            tenant_id=tenant_id,
            new_number=1000,  # already in use
        )
    assert "already in use" in str(exc_info.value)


def test_reassign_parent(db):
    """Reassign parent of an account."""
    user, tenant_id = _seed_tenant_and_user(db)
    parent = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    child = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1010",
        name="Operating Checking",
        account_type="asset",
    )
    # Initially no parent
    assert child["parent_id"] is None

    # Assign parent
    updated = reassign_parent(
        db=db,
        account_id=child["id"],
        tenant_id=tenant_id,
        new_parent_id=parent["id"],
    )
    assert updated["parent_id"] == parent["id"]

    # Clear parent
    updated = reassign_parent(
        db=db,
        account_id=child["id"],
        tenant_id=tenant_id,
        new_parent_id=None,
    )
    assert updated["parent_id"] is None


def test_reassign_parent_rejects_self_parent(db):
    """Cannot assign account as its own parent."""
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    with pytest.raises(Exception) as exc_info:
        reassign_parent(
            db=db,
            account_id=created["id"],
            tenant_id=tenant_id,
            new_parent_id=created["id"],
        )
    assert "cannot be its own parent" in str(exc_info.value)


def test_tenant_isolation(db):
    """User A cannot see User B's COA accounts."""
    user_a, tenant_a = _seed_tenant_and_user(db)
    user_b, tenant_b = _seed_tenant_and_user_b(db)

    # Create account in tenant A
    create_account(
        db=db,
        tenant_id=tenant_a,
        user_id=user_a.id,
        code="1000",
        name="Tenant A Cash",
        account_type="asset",
    )

    # Tenant B should see no accounts
    accounts_b = get_accounts(db, tenant_id=tenant_b, user_id=user_b.id)
    assert accounts_b == []

    # Create account in tenant B
    create_account(
        db=db,
        tenant_id=tenant_b,
        user_id=user_b.id,
        code="1000",
        name="Tenant B Cash",
        account_type="asset",
    )
    accounts_b = get_accounts(db, tenant_id=tenant_b, user_id=user_b.id)
    assert len(accounts_b) == 1
    assert accounts_b[0]["name"] == "Tenant B Cash"

    # Tenant A still only sees its own
    accounts_a = get_accounts(db, tenant_id=tenant_a, user_id=user_a.id)
    assert len(accounts_a) == 1
    assert accounts_a[0]["name"] == "Tenant A Cash"


def test_get_account_single(db):
    """get_account returns the account dict or None."""
    user, tenant_id = _seed_tenant_and_user(db)
    created = create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=user.id,
        code="1000",
        name="Cash",
        account_type="asset",
    )
    found = get_account(db, account_id=created["id"], tenant_id=tenant_id)
    assert found is not None
    assert found["id"] == created["id"]
    assert get_account(db, account_id=99999, tenant_id=tenant_id) is None


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


def test_api_coa_seed(auth_client: TestClient):
    """Test the COA seed endpoint."""
    c = auth_client

    # Create tenant
    resp = c.post("/api/clients/", json={"name": "Seed Client"})
    assert resp.status_code == 200

    # Seed COA
    resp = c.post("/api/coa/seed")
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) > 10

    # Double seed should fail
    resp = c.post("/api/coa/seed")
    assert resp.status_code == 409


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
                user_id=1,
                filename="stmt.pdf",
            )
            db.add(statement)
            db.commit()
            db.refresh(statement)

        txn = models.Transaction(
            statement_id=statement.id,
            tenant_id=tenant_id,
            user_id=statement.user_id,
            coa_account_id=coa_id,
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
