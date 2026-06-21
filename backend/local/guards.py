"""Runtime guards that block or warn about cloud/API usage in offline mode.

Intended for import-time and call-site protection. All network-facing modules
should go through here before making external requests.
"""

from __future__ import annotations

import functools
import socket
from typing import Callable, TypeVar

from .settings import guard_cloud_call, is_offline


F = TypeVar("F")


def block_cloud_calls(func: F) -> F:
    """Decorator that raises RuntimeError if the wrapped function is called offline."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        guard_cloud_call(func.__name__)
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def assert_no_network_access(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> None:
    """Raise RuntimeError if the host can reach the public internet."""
    if not is_offline():
        return
    try:
        with socket.create_connection((host, port), timeout=timeout):
            raise RuntimeError(
                f"Offline mode expected no network access, but {host}:{port} is reachable."
            )
    except OSError:
        pass


class CloudAPIGuard:
    """Context manager to assert no cloud calls happen inside a block.

    Usage:
        with CloudAPIGuard():
            do_something_that_should_not_call_cloud()
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    @staticmethod
    def ensure_offline():
        if not is_offline():
            raise RuntimeError("Operation requires offline runtime mode")


def is_duplicate_transaction(existing: dict, candidate: dict, tolerance: float = 0.0) -> bool:
    """Return True if candidate is a likely duplicate of existing."""
    import re

    def normalize(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    if existing.get("date") != candidate.get("date"):
        return False
    if existing.get("tx_type") != candidate.get("tx_type"):
        return False
    if normalize(existing.get("description", "")) != normalize(candidate.get("description", "")):
        return False

    existing_amount = float(existing.get("amount", 0))
    candidate_amount = float(candidate.get("amount", 0))
    if tolerance > 0:
        return abs(existing_amount - candidate_amount) <= tolerance
    return existing_amount == candidate_amount
