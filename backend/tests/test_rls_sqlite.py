"""Stub tests for SQLite fallback tenant scoping.

Expected coverage (v3.11.5):
- ``backend.rls`` helpers are no-ops on SQLite.
- Application-level tenant filtering is applied in all router queries.
- A row in tenant A is not returned when the request context is tenant B.

These tests are stubs because the SQLite fallback relies on application-level
query filtering that will be hardened alongside the PostgreSQL RLS policies.
"""
from __future__ import annotations

import pytest


def test_sqlite_rls_helpers_noop():
    """Placeholder: RLS helpers must not raise on SQLite sessions."""
    from backend import rls

    assert rls.is_postgres() is False


def test_sqlite_tenant_filtering_stub():
    """Placeholder: application-level tenant filtering is enforced."""
    # TODO(v3.11.5): add a test that creates two clients and confirms a router
    # only returns data for the active tenant.
    pass
