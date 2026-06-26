"""Production-mode behavior tests.

Covers:
- ``TAXFLOW_ENV=production`` makes ``local_settings.is_production()`` True.
- ``/api/tests/`` returns 404 in production.
- ``/api/health`` reports ``production_mode: true`` in production and
  ``production_mode: false`` in development.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def prod_env(monkeypatch):
    """Set the active environment to production for one test."""
    monkeypatch.setenv("TAXFLOW_ENV", "production")
    # The settings module reads dynamically, but the api module captures
    # ENVIRONMENT at import time. We reload both so the test sees prod mode.
    import backend.local.settings as settings
    import backend.api as api
    from importlib import reload
    reload(settings)
    reload(api)
    yield settings, api
    # Restore development default after the test.
    monkeypatch.setenv("TAXFLOW_ENV", "development")
    reload(settings)
    reload(api)


def test_production_env_flag():
    """``TAXFLOW_ENV=production`` sets ``is_production()`` True."""
    import backend.local.settings as settings
    from importlib import reload

    # Default test environment from conftest is development.
    assert settings.is_development() is True
    assert settings.is_production() is False

    os.environ["TAXFLOW_ENV"] = "production"
    try:
        reload(settings)
        assert settings.is_production() is True
        assert settings.is_development() is False
    finally:
        os.environ["TAXFLOW_ENV"] = "development"
        reload(settings)


def test_api_tests_returns_404_in_production(prod_env):
    """The test-runner router is absent in production builds."""
    _settings, api = prod_env
    client = TestClient(api.app)
    resp = client.get("/api/tests/")
    assert resp.status_code == 404


def test_api_health_reports_production_mode(prod_env):
    """``/api/health`` reports production_mode: true in production."""
    _settings, api = prod_env
    client = TestClient(api.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["environment"] == "production"
    assert data["production_mode"] is True


def test_api_health_reports_development_mode(client):
    """``/api/health`` reports production_mode: false in development."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["environment"] == "development"
    assert data["production_mode"] is False
