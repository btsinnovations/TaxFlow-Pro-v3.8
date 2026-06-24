"""Global per-IP sliding-window rate limiter.

This is intentionally in-memory and stateless across process restarts. It is
meant to blunt abuse of the public API surface, not to enforce hard quotas for
a multi-process deployment (which would require a shared store such as Redis).
"""
from __future__ import annotations

import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from fastapi import HTTPException, status


#: Default global rate limit: requests per window.
DEFAULT_LIMIT = 100
#: Default window length in seconds.
DEFAULT_WINDOW = 60
#: Default burst allowance before the rate limiter starts delaying/blocking.
DEFAULT_BURST = 10


_parse_re = re.compile(r"^(\d+)\s*/\s*(\d+)?\s*(second|minute|hour|day)s?$", re.IGNORECASE)


def _parse_limit(value: str) -> tuple[int, int]:
    """Parse a limit string like ``100/minute`` into (limit, window_seconds)."""
    value = value.strip()
    match = _parse_re.match(value)
    if not match:
        raise ValueError(
            f"Invalid rate limit format: {value!r}. Expected format: N/UNIT "
            "where UNIT is second, minute, hour, or day."
        )
    count = int(match.group(1))
    multiplier = int(match.group(2) or 1)
    unit = match.group(3).lower()
    unit_seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit]
    return count, multiplier * unit_seconds


@dataclass
class _Window:
    """Sliding window state for a single client key."""

    limit: int
    window: float
    burst: int
    requests: deque[float] = field(default_factory=deque)
    lock: Lock = field(default_factory=Lock)

    def is_allowed(self, now: Optional[float] = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = now or time.monotonic()
        cutoff = now - self.window
        with self.lock:
            # Drop requests outside the current window.
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            # Burst lets the first N requests through unconditionally.
            if len(self.requests) < self.burst:
                self.requests.append(now)
                return True, 0
            # Beyond burst, enforce the average rate.
            if len(self.requests) < self.limit:
                self.requests.append(now)
                return True, 0
            # Window is full; tell the client when the oldest request expires.
            retry_after = max(1, int(self.requests[0] - cutoff + 1))
            return False, retry_after


class GlobalRateLimiter:
    """In-memory sliding-window rate limiter keyed by client identifier."""

    def __init__(
        self,
        limit: int = DEFAULT_LIMIT,
        window: int = DEFAULT_WINDOW,
        burst: int = DEFAULT_BURST,
        trusted_proxy_hops: int = 0,
    ) -> None:
        self.limit = limit
        self.window = window
        self.burst = burst
        self.trusted_proxy_hops = trusted_proxy_hops
        self._windows: dict[str, _Window] = {}
        self._lock = Lock()

    @classmethod
    def from_env(cls) -> "GlobalRateLimiter":
        """Build a limiter from environment variables."""
        env_limit = os.environ.get("TAXFLOW_GLOBAL_RATE_LIMIT", f"{DEFAULT_LIMIT}/minute")
        try:
            limit, window = _parse_limit(env_limit)
        except ValueError:
            limit, window = DEFAULT_LIMIT, DEFAULT_WINDOW
        burst = int(os.environ.get("TAXFLOW_GLOBAL_BURST_LIMIT", str(DEFAULT_BURST)))
        hops = int(os.environ.get("TAXFLOW_TRUSTED_PROXY_HOPS", "0"))
        return cls(limit=limit, window=window, burst=burst, trusted_proxy_hops=hops)

    def _client_key(self, remote_addr: Optional[str], headers: dict[str, str]) -> str:
        """Choose a stable key for rate-limit accounting.

        If ``trusted_proxy_hops`` > 0, the client address in ``X-Forwarded-For``
        is used. X-Forwarded-For is ordered client, proxy1, proxy2, ...; with
        ``trusted_proxy_hops=N`` we trust the rightmost N entries and use the
        address immediately to their left, i.e. index ``-(N+1)``. Otherwise the
        direct remote address is used to prevent spoofing.
        """
        if self.trusted_proxy_hops > 0:
            forwarded = headers.get("x-forwarded-for", "")
            if forwarded:
                parts = [p.strip() for p in forwarded.split(",") if p.strip()]
                try:
                    return parts[-(self.trusted_proxy_hops + 1)]
                except IndexError:
                    pass
        return remote_addr or "unknown"

    def _get_window(self, key: str) -> _Window:
        with self._lock:
            if key not in self._windows:
                self._windows[key] = _Window(
                    limit=self.limit,
                    window=self.window,
                    burst=self.burst,
                )
            return self._windows[key]

    def check(self, remote_addr: Optional[str], headers: dict[str, str]) -> None:
        """Raise HTTPException(429) if the client has exceeded its limit."""
        key = self._client_key(remote_addr, headers)
        window = self._get_window(key)
        allowed, retry_after = window.is_allowed()
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": str(retry_after)},
            )
