"""Tests for TASK-027: security headers + CORS hardening."""

import os

import pytest


# CORS preflight remains functional for the allowed local dev origin.
def test_cors_preflight_allowed_origin(client):
    resp = client.options(
        "/api/auth/register",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in resp.headers.get("access-control-allow-methods", "")
    assert "content-type" in resp.headers.get("access-control-allow-headers", "")


# Disallowed origins must be rejected at the CORS preflight layer.
def test_cors_preflight_disallowed_origin(client):
    resp = client.options(
        "/api/auth/register",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


# Actual cross-origin GET responses only carry allow-origin for allowed origins.
def test_cors_get_allowed_origin(client):
    resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_get_disallowed_origin(client):
    from backend.tests.test_global_rate_limit import _reset_global_limiter

    _reset_global_limiter(tight_limit=100, window=60, burst=10)
    resp = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


# Security headers are present on both API and non-API responses.
@pytest.mark.parametrize("path", ["/health", "/api/health"])
def test_security_headers(client, path):
    from backend.tests.test_global_rate_limit import _reset_global_limiter

    _reset_global_limiter(tight_limit=100, window=60, burst=10)
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in resp.headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in resp.headers.get("Content-Security-Policy", "")


# HSTS is only added in production mode.
def test_hsts_absent_in_development(client):
    from backend.tests.test_global_rate_limit import _reset_global_limiter

    _reset_global_limiter(tight_limit=100, window=60, burst=10)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "Strict-Transport-Security" not in resp.headers


def test_hsts_present_in_production(monkeypatch):
    """Reload the app factory with TAXFLOW_ENVIRONMENT=production and verify HSTS.

    We import inside the test and patch the environment before creating a new
    FastAPI instance so the production-only header path is exercised.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("TAXFLOW_ENVIRONMENT", "production")
    # Re-import settings so ENVIRONMENT picks up the new env value.
    from backend import local
    import importlib

    importlib.reload(local.settings)

    # Rebuild the app to capture the new settings.
    from backend import api
    importlib.reload(api)

    from backend.tests.test_global_rate_limit import _reset_global_limiter

    _reset_global_limiter(tight_limit=100, window=60, burst=10)

    with TestClient(api.app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200
        hsts = resp.headers.get("Strict-Transport-Security")
        assert hsts == "max-age=31536000; includeSubDomains"


# TAXFLOW_CORS_ORIGINS env override is respected.
def test_cors_origins_env_override(client, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import local
    import importlib

    monkeypatch.setenv("TAXFLOW_CORS_ORIGINS", "http://localhost:9999")
    importlib.reload(local.settings)
    from backend import api
    importlib.reload(api)

    from backend.tests.test_global_rate_limit import _reset_global_limiter

    _reset_global_limiter(tight_limit=100, window=60, burst=10)

    with TestClient(api.app) as c:
        resp = c.options(
            "/api/auth/register",
            headers={
                "Origin": "http://localhost:9999",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:9999"

        resp = c.options(
            "/api/auth/register",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 400
        assert "access-control-allow-origin" not in resp.headers
