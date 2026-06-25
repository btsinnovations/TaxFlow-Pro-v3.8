"""Tests for v3.11 tax rules search/filter/sort API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import CategorizationRuleCreate


def _seed_gl_account(db: Session, tenant_id: int, user_id: int):
    account = models.GLAccount(
        tenant_id=tenant_id,
        user_id=user_id,
        code="6100",
        name="Advertising",
        account_type="expense",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _seed_rules(db: Session, tenant_id: int, user_id: int, gl_account_id: int):
    rules = [
        models.CategorizationRule(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Advertising - Google",
            pattern="google ads",
            form="Schedule C",
            line="Advertising",
            gl_account_id=gl_account_id,
            priority=10,
            enabled=True,
        ),
        models.CategorizationRule(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Office Supplies",
            pattern="staples|office depot",
            form="Schedule C",
            line="Office",
            gl_account_id=gl_account_id,
            priority=5,
            enabled=True,
        ),
        models.CategorizationRule(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Disabled Rule",
            pattern="disabled pattern",
            form="Schedule E",
            line="Misc",
            gl_account_id=gl_account_id,
            priority=99,
            enabled=False,
        ),
        models.CategorizationRule(
            tenant_id=tenant_id,
            user_id=user_id,
            name="Meals",
            pattern="restaurant",
            form="Schedule C",
            line="Meals",
            gl_account_id=gl_account_id,
            priority=7,
            enabled=True,
        ),
    ]
    db.add_all(rules)
    db.commit()
    return rules


def _auth_tenant(db: Session):
    user = db.query(models.User).filter(models.User.username == "testuser").first()
    assert user is not None
    client = user.clients[0]
    return user, client


def test_search_by_name_pattern(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    gl = _seed_gl_account(db, client.id, user.id)
    _seed_rules(db, client.id, user.id, gl.id)

    resp = auth_client.get("/api/tax-rules?query=google")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Advertising - Google"

    resp = auth_client.get("/api/tax-rules?query=office")
    assert resp.status_code == 200
    assert any(r["name"] == "Office Supplies" for r in resp.json())


def test_filter_by_form_and_line(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    gl = _seed_gl_account(db, client.id, user.id)
    _seed_rules(db, client.id, user.id, gl.id)

    resp = auth_client.get("/api/tax-rules?form=Schedule+C&line=Advertising")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["line"] == "Advertising"


def test_filter_by_enabled_status(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    gl = _seed_gl_account(db, client.id, user.id)
    _seed_rules(db, client.id, user.id, gl.id)

    resp = auth_client.get("/api/tax-rules?enabled=true")
    assert resp.status_code == 200, resp.text
    assert all(r["enabled"] for r in resp.json())
    assert len(resp.json()) == 3

    resp = auth_client.get("/api/tax-rules?enabled=false")
    assert resp.status_code == 200
    assert all(not r["enabled"] for r in resp.json())
    assert len(resp.json()) == 1


def test_sort_by_priority(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    gl = _seed_gl_account(db, client.id, user.id)
    _seed_rules(db, client.id, user.id, gl.id)

    resp = auth_client.get("/api/tax-rules?sort=priority&order=desc&enabled=true")
    assert resp.status_code == 200, resp.text
    priorities = [r["priority"] for r in resp.json()]
    assert priorities == sorted(priorities, reverse=True)

    resp = auth_client.get("/api/tax-rules?sort=priority&order=asc&enabled=true")
    assert resp.status_code == 200
    priorities = [r["priority"] for r in resp.json()]
    assert priorities == sorted(priorities)


def test_sort_by_pattern_length(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    gl = _seed_gl_account(db, client.id, user.id)
    _seed_rules(db, client.id, user.id, gl.id)

    resp = auth_client.get("/api/tax-rules?sort=pattern_length&order=asc&enabled=true")
    assert resp.status_code == 200, resp.text
    lengths = [len(r["pattern"]) for r in resp.json()]
    assert lengths == sorted(lengths)


def test_search_empty_state(auth_client: TestClient, db: Session):
    user, client = _auth_tenant(db)
    gl = _seed_gl_account(db, client.id, user.id)
    _seed_rules(db, client.id, user.id, gl.id)

    resp = auth_client.get("/api/tax-rules?query=nonexistentzzzz")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
