"""Tests for the global request body size limit middleware (TASK-031)."""

from __future__ import annotations

import pytest
from starlette.requests import Request as StarletteRequest

from backend.api import _RequestSizeLimitMiddleware
from backend.security import request_validation


@pytest.fixture(autouse=True)
def _reset_body_limit(monkeypatch):
    """Reset the body limit to a small, predictable value for each test."""
    monkeypatch.setattr(request_validation, "MAX_BODY_SIZE_BYTES", 1024)
    yield


async def _noop_call_next(request: StarletteRequest):
    class _FakeResponse:
        status_code = 200
        headers = {}
    return _FakeResponse()


def test_small_json_request_succeeds():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/clients/",
        "headers": [(b"content-length", b"64")],
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 200

    import asyncio
    asyncio.run(_run())


def test_oversized_json_body_rejected():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/clients/",
        "headers": [(b"content-length", b"2048")],
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 413
        assert resp.headers.get("Retry-After") == "1024"
        assert b"exceeds maximum size" in resp.body

    import asyncio
    asyncio.run(_run())


def test_upload_route_exempt_from_general_body_limit():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/upload",
        "headers": [(b"content-length", b"33554432")],  # 32 MiB
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 200

    import asyncio
    asyncio.run(_run())


def test_missing_content_length_passes_through():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/clients/",
        "headers": [],
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 200

    import asyncio
    asyncio.run(_run())


def test_invalid_content_length_rejected():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/clients/",
        "headers": [(b"content-length", b"not-a-number")],
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 400
        assert b"Invalid Content-Length" in resp.body

    import asyncio
    asyncio.run(_run())


def test_negative_content_length_rejected():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/clients/",
        "headers": [(b"content-length", b"-1")],
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 400
        assert b"Invalid Content-Length" in resp.body

    import asyncio
    asyncio.run(_run())


def test_zero_content_length_succeeds():
    middleware = _RequestSizeLimitMiddleware(app=None)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/clients/",
        "headers": [(b"content-length", b"0")],
        "query_string": b"",
    }
    request = StarletteRequest(scope, receive=None)

    async def _run():
        resp = await middleware.dispatch(request, _noop_call_next)
        assert resp.status_code == 200

    import asyncio
    asyncio.run(_run())


from fastapi.testclient import TestClient


def test_oversized_json_integration(client):
    """End-to-end: a JSON body larger than the general limit is rejected with 413."""
    original_limit = request_validation.MAX_BODY_SIZE_BYTES
    request_validation.MAX_BODY_SIZE_BYTES = 64
    try:
        resp = client.post(
            "/api/auth/register",
            json={"username": "x", "email": "x@example.com", "password": "y" * 256},
            headers={"Content-Length": "1024"},
        )
        assert resp.status_code == 413
        assert resp.headers.get("retry-after") == "64"
        assert "exceeds maximum size" in resp.json()["detail"]
    finally:
        request_validation.MAX_BODY_SIZE_BYTES = original_limit

