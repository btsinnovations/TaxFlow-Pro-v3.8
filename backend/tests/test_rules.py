"""Tests for the categorization rule engine."""
from __future__ import annotations

from datetime import date

from backend import models
from backend.services.rules import apply_rules
from backend.tests.conftest import TestingSessionLocal


def _seed_tenant_user_account(client) -> tuple:
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == "testuser").first()
        if user is None:
            user = models.User(
                username="testuser",
                email="test@example.com",
                hashed_password="fakehash",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        client_obj = models.Client(name="Test Client", user_id=user.id)
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)
        account = models.Account(
            name="Checking",
            institution="Test Bank",
            type="checking",
            client_id=client_obj.id,
            tenant_id=client_obj.id,
            user_id=user.id,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return user.id, client_obj.id, account.id
    finally:
        db.close()


def _seed_gl_account(tenant_id: int, user_id: int, code: str, name: str, account_type: str = "expense"):
    db = TestingSessionLocal()
    try:
        acct = models.GLAccount(
            tenant_id=tenant_id, user_id=user_id, code=code, name=name, account_type=account_type
        )
        db.add(acct)
        db.commit()
        db.refresh(acct)
        return acct.id
    finally:
        db.close()


def _seed_transactions(account_id: int, tenant_id: int, user_id: int, descriptions: list):
    db = TestingSessionLocal()
    try:
        stmt = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="test.pdf",
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
        txs = []
        for desc in descriptions:
            tx = models.Transaction(
                statement_id=stmt.id,
                tenant_id=tenant_id,
                user_id=user_id,
                date=date(2025, 1, 15),
                description=desc,
                amount="10.00",
                tx_type="debit",
            )
            db.add(tx)
            txs.append(tx)
        db.commit()
        for tx in txs:
            db.refresh(tx)
        return txs
    finally:
        db.close()


def test_create_rule_and_apply_to_matching_transaction(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant_user_account(client)
    acct_id = _seed_gl_account(tenant_id, user_id, "6000", "Office Supplies")

    resp = client.post("/api/rules/", params={"tenant_id": tenant_id}, json={
        "name": "Office Supplies",
        "pattern": "staples",
        "gl_account_id": acct_id,
        "priority": 1,
        "enabled": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Office Supplies"
    assert data["gl_account_id"] == acct_id

    txs = _seed_transactions(account_id, tenant_id, user_id, ["Staples purchase"])
    db = TestingSessionLocal()
    try:
        rules = db.query(models.CategorizationRule).filter(
            models.CategorizationRule.tenant_id == tenant_id
        ).all()
        apply_rules(txs, rules)
        assert txs[0].category == "Office Supplies"
        assert txs[0].gl_account_id == acct_id
    finally:
        db.close()


def test_priority_tie_breaking(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant_user_account(client)
    acct_low_id = _seed_gl_account(tenant_id, user_id, "6100", "General Expense")
    acct_high_id = _seed_gl_account(tenant_id, user_id, "6200", "Specific Expense")

    client.post("/api/rules/", params={"tenant_id": tenant_id}, json={
        "name": "Low",
        "pattern": "vendor",
        "gl_account_id": acct_low_id,
        "priority": 1,
    })
    client.post("/api/rules/", params={"tenant_id": tenant_id}, json={
        "name": "High",
        "pattern": "vendor",
        "gl_account_id": acct_high_id,
        "priority": 5,
    })

    txs = _seed_transactions(account_id, tenant_id, user_id, ["Vendor charge"])
    db = TestingSessionLocal()
    try:
        rules = db.query(models.CategorizationRule).filter(
            models.CategorizationRule.tenant_id == tenant_id
        ).all()
        apply_rules(txs, rules)
        assert txs[0].gl_account_id == acct_high_id
        assert txs[0].category == "High"
    finally:
        db.close()


def test_no_match_leaves_transaction_uncategorized(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant_user_account(client)
    acct_id = _seed_gl_account(tenant_id, user_id, "6000", "Office Supplies")

    client.post("/api/rules/", params={"tenant_id": tenant_id}, json={
        "name": "Office Supplies",
        "pattern": "staples",
        "gl_account_id": acct_id,
    })

    txs = _seed_transactions(account_id, tenant_id, user_id, ["Unknown merchant"])
    db = TestingSessionLocal()
    try:
        rules = db.query(models.CategorizationRule).filter(
            models.CategorizationRule.tenant_id == tenant_id
        ).all()
        apply_rules(txs, rules)
        assert txs[0].category == "uncategorized"
        assert txs[0].gl_account_id is None
    finally:
        db.close()


def test_disabled_rule_is_ignored(auth_client):
    client = auth_client
    user_id, tenant_id, account_id = _seed_tenant_user_account(client)
    acct_id = _seed_gl_account(tenant_id, user_id, "6000", "Office Supplies")

    resp = client.post("/api/rules/", params={"tenant_id": tenant_id}, json={
        "name": "Office Supplies",
        "pattern": "staples",
        "gl_account_id": acct_id,
        "enabled": False,
    })
    assert resp.status_code == 200

    txs = _seed_transactions(account_id, tenant_id, user_id, ["Staples purchase"])
    db = TestingSessionLocal()
    try:
        rules = db.query(models.CategorizationRule).filter(
            models.CategorizationRule.tenant_id == tenant_id
        ).all()
        apply_rules(txs, rules)
        assert txs[0].category == "uncategorized"
    finally:
        db.close()


def test_update_and_delete_rule(auth_client):
    client = auth_client
    user_id, tenant_id, _ = _seed_tenant_user_account(client)
    acct_id = _seed_gl_account(tenant_id, user_id, "6000", "Office Supplies")

    resp = client.post("/api/rules/", params={"tenant_id": tenant_id}, json={
        "name": "Office Supplies",
        "pattern": "staples",
        "gl_account_id": acct_id,
    })
    rule_id = resp.json()["id"]

    resp = client.put(f"/api/rules/{rule_id}", params={"tenant_id": tenant_id}, json={
        "pattern": "office depot",
        "priority": 10,
    })
    assert resp.status_code == 200
    assert resp.json()["pattern"] == "office depot"
    assert resp.json()["priority"] == 10

    resp = client.delete(f"/api/rules/{rule_id}", params={"tenant_id": tenant_id})
    assert resp.status_code == 200
    resp = client.get(f"/api/rules/{rule_id}", params={"tenant_id": tenant_id})
    assert resp.status_code == 404
