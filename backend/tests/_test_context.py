"""Shared per-test context registry for the bulletproof test harness.

This module exists so the registry is a true singleton even if pytest imports
``conftest.py`` through multiple paths. Do not import this directly from tests;
use the proxies exposed by ``backend.tests.conftest``.
"""
from __future__ import annotations

import threading
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient


class _TestContext:
    __slots__ = ("engine", "SessionLocal", "override_get_db", "client", "db_url")

    def __init__(
        self,
        engine: "Engine",
        SessionLocal: "sessionmaker",
        override_get_db,
        client: "TestClient",
        db_url: str,
    ):
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.override_get_db = override_get_db
        self.client = client
        self.db_url = db_url


# Protected global pointer to the currently active test's engine/session.
# Tests run sequentially under pytest by default, so a single global context
# is sufficient and avoids the module-duplication issue with conftest imports.
_current_context: _TestContext | None = None
_context_lock = threading.Lock()


def get_active_context() -> _TestContext:
    ctx = _current_context
    if ctx is None:
        raise RuntimeError(
            "No active test context. "
            "Accessing conftest.engine/TestingSessionLocal/override_get_db "
            "outside of a test (or before the client/db fixture is active)."
        )
    return ctx


def set_active_context(ctx: _TestContext | None) -> None:
    global _current_context
    with _context_lock:
        _current_context = ctx


def active_engine() -> "Engine":
    return get_active_context().engine


def active_sessionlocal() -> "sessionmaker":
    return get_active_context().SessionLocal


def active_override_get_db():
    return get_active_context().override_get_db()
