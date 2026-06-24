"""Single-user default mode tests (TASK-038.14)."""
from __future__ import annotations

import os

import pytest


class TestSingleUserSettings:
    def test_single_user_mode_default_true(self):
        """TAXFLOW_SINGLE_USER defaults to true when not explicitly overridden."""
        import importlib

        os.environ.pop("TAXFLOW_SINGLE_USER", None)
        from backend.local import settings
        importlib.reload(settings)
        assert settings.is_single_user() is True

    def test_single_user_explicit_false(self, monkeypatch):
        monkeypatch.setenv("TAXFLOW_SINGLE_USER", "false")
        import importlib
        from backend.local import settings
        importlib.reload(settings)
        assert settings.is_single_user() is False


class TestNoTenantHeaderRequired:
    def test_no_tenant_header_required_for_single_user_sqlite(self, auth_client, monkeypatch):
        """A single-user SQLite request without X-Tenant-ID succeeds."""
        monkeypatch.setenv("TAXFLOW_SINGLE_USER", "true")
        auth_client.headers.pop("X-Tenant-ID", None)
        resp = auth_client.get("/api/health/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["single_user"] is True

    def test_x_tenant_id_header_ignored_in_single_user_sqlite(self, auth_client, monkeypatch):
        """An arbitrary X-Tenant-ID header is ignored in single-user SQLite mode."""
        monkeypatch.setenv("TAXFLOW_SINGLE_USER", "true")
        auth_client.headers["X-Tenant-ID"] = "9999"
        resp = auth_client.get("/api/health/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["single_user"] is True


class TestMultiEntityRequiresHeader:
    def test_multi_entity_mode_requires_tenant_header_on_postgres(self, auth_client, monkeypatch):
        """Multi-entity mode on PostgreSQL requires the X-Tenant-ID header."""
        # The app module already imported is_postgres; monkeypatch the function
        # object used by the middleware to return True regardless of DATABASE_URL.
        monkeypatch.setenv("TAXFLOW_SINGLE_USER", "false")
        monkeypatch.setattr("backend.api.is_postgres", lambda: True)
        import importlib
        from backend.local import settings
        importlib.reload(settings)
        assert settings.is_single_user() is False

        auth_client.headers.pop("X-Tenant-ID", None)
        resp = auth_client.get("/api/health/config")
        assert resp.status_code == 400
        assert "X-Tenant-ID" in resp.json()["detail"]
