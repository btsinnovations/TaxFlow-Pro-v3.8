"""Tests for PostgreSQL Row-Level Security helpers.

These tests validate the helper API on SQLite and the shape of the policy
migration. Full policy enforcement requires a live PostgreSQL instance.
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend import rls
from backend.database import Base, get_db


def test_is_postgres_false_for_sqlite():
    assert not rls.is_postgres()


def test_is_postgres_true_for_postgresql(monkeypatch):
    monkeypatch.setattr(rls, "DATABASE_URL", "postgresql://user:pass@localhost/db")
    assert rls.is_postgres()


def test_set_tenant_id_noop_on_sqlite(tmp_path):
    db_path = tmp_path / "rls.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        # Must not raise on SQLite.
        rls.set_tenant_id(session, tenant_id=1)
        rls.clear_tenant_id(session)
    finally:
        session.close()


def test_tenant_scope_context_manager(tmp_path, monkeypatch):
    """TenantScope enters and exits cleanly on SQLite (no-op)."""
    db_path = tmp_path / "scope.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        with rls.TenantScope(session, tenant_id=42) as scoped:
            assert scoped is session
    finally:
        session.close()


def test_middleware_sets_request_state_for_postgresql(monkeypatch):
    """Middleware should set request.state.tenant_id when X-Tenant-ID is present."""
    from fastapi import Request
    from fastapi.testclient import TestClient
    from backend.api import app

    monkeypatch.setattr(rls, "DATABASE_URL", "postgresql://localhost/fake")

    @app.get("/__rls_test__")
    def capture_state(request: Request):
        return {"tenant_id": getattr(request.state, "tenant_id", "missing")}

    with TestClient(app) as client:
        resp = client.get("/__rls_test__", headers={"X-Tenant-ID": "7"})
        assert resp.status_code == 200, resp.text
        assert resp.json().get("tenant_id") == 7
    # Remove the temporary route to avoid polluting the shared app.
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/__rls_test__"]
    app.openapi_schema = None


def test_middleware_invalid_tenant_header(monkeypatch):
    from fastapi import Request
    from fastapi.testclient import TestClient
    from backend.api import app

    monkeypatch.setattr(rls, "DATABASE_URL", "postgresql://localhost/fake")

    @app.get("/__rls_test_invalid__")
    def capture_invalid(request: Request):
        return {"tenant_id": getattr(request.state, "tenant_id", "missing")}

    with TestClient(app) as client:
        resp = client.get("/__rls_test_invalid__", headers={"X-Tenant-ID": "not-a-number"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["tenant_id"] is None
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/__rls_test_invalid__"]
    app.openapi_schema = None


def test_rls_migration_file_exists():
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "b9f4e2c8d310_enable_postgresql_row_level_security.py"
    assert migration_path.exists()
    content = migration_path.read_text()
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "current_setting('taxflow.tenant_id', true)" in content or "taxflow.tenant_id_matches" in content
