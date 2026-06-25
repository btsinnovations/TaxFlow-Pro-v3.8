"""Tests for TASK-028: global per-IP sliding-window rate limiting."""

import time

import pytest

from backend import api
from backend.rate_limit import GlobalRateLimiter


def _reset_global_limiter(tight_limit: int = 1, window: int = 60, burst: int = 0) -> None:
    """Replace the global limiter in api with a deterministic instance."""
    api._GLOBAL_RATE_LIMITER = GlobalRateLimiter(
        limit=tight_limit,
        window=window,
        burst=burst,
        trusted_proxy_hops=0,
    )
    # Tell the limiter this test explicitly wants enforcement, so the test
    # bypass in `check()` does not short-circuit.
    api._GLOBAL_RATE_LIMITER._test_enforce = True


def test_default_rate_limit_allows_reasonable_volume(client):
    """Under default settings the first burst of requests should succeed."""
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_custom_rate_limit_rejects_excess_requests(client):
    """With a very tight limit, requests beyond the allowance are rejected with 429."""
    _reset_global_limiter(tight_limit=1, window=60, burst=0)

    # First request is allowed.
    resp = client.get("/health")
    assert resp.status_code == 200

    # Second request in the same window is rejected.
    resp = client.get("/health")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.json()["detail"] == "Rate limit exceeded. Please slow down."


def test_rate_limit_window_allows_retry_after_expiry(client):
    """After the window slides, requests are allowed again."""
    _reset_global_limiter(tight_limit=1, window=1, burst=0)

    resp = client.get("/health")
    assert resp.status_code == 200

    resp = client.get("/health")
    assert resp.status_code == 429

    time.sleep(1.1)

    resp = client.get("/health")
    assert resp.status_code == 200


def test_x_forwarded_for_only_when_trusted():
    """X-Forwarded-For is ignored unless TAXFLOW_TRUSTED_PROXY_HOPS is set."""
    from backend.rate_limit import GlobalRateLimiter

    limiter = GlobalRateLimiter.from_env()
    assert limiter.trusted_proxy_hops == 0

    # Without trusted hops, the header is ignored and the direct address is used.
    key = limiter._client_key("10.0.0.1", {"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert key == "10.0.0.1"


def test_x_forwarded_for_used_when_trusted():
    """With trusted hops, the client address in X-Forwarded-For is used."""
    from backend.rate_limit import GlobalRateLimiter

    limiter = GlobalRateLimiter(
        limit=1,
        window=60,
        burst=0,
        trusted_proxy_hops=2,
    )
    # Header is "client, proxy1, proxy2". With 2 trusted proxies, the client
    # is immediately to the left of the trusted block: proxy2 is the last entry,
    # so the client is at index -(2+1) = -3.
    key = limiter._client_key("10.0.0.1", {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 9.10.11.12"})
    assert key == "1.2.3.4"


def test_parse_limit_formats():
    """Rate-limit string parsing handles seconds, minutes, hours, and days."""
    from backend.rate_limit import _parse_limit

    assert _parse_limit("100/minute") == (100, 60)
    assert _parse_limit("5 / second") == (5, 1)
    assert _parse_limit("10 / 2 hours") == (10, 7200)
    assert _parse_limit("1000/day") == (1000, 86400)


def test_parse_limit_rejects_bad_format():
    """Malformed rate-limit strings raise a clear ValueError."""
    from backend.rate_limit import _parse_limit

    with pytest.raises(ValueError):
        _parse_limit("not-a-limit")


def test_limiter_env_override(monkeypatch):
    """TAXFLOW_GLOBAL_RATE_LIMIT and TAXFLOW_GLOBAL_BURST_LIMIT are parsed."""
    from backend.rate_limit import GlobalRateLimiter

    monkeypatch.setenv("TAXFLOW_GLOBAL_RATE_LIMIT", "50/2 minutes")
    monkeypatch.setenv("TAXFLOW_GLOBAL_BURST_LIMIT", "5")
    limiter = GlobalRateLimiter.from_env()
    assert limiter.limit == 50
    assert limiter.window == 120
    assert limiter.burst == 5


def test_trusted_proxy_hops_env_override(monkeypatch):
    """TAXFLOW_TRUSTED_PROXY_HOPS configures proxy trust depth."""
    from backend.rate_limit import GlobalRateLimiter

    monkeypatch.setenv("TAXFLOW_TRUSTED_PROXY_HOPS", "2")
    limiter = GlobalRateLimiter.from_env()
    assert limiter.trusted_proxy_hops == 2
