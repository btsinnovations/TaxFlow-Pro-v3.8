"""Stub tests for PostgreSQL Row-Level Security policies.

Expected coverage (v3.11.5):
- PostgreSQL policies exist for all tenant-isolated tables.
- A row in tenant A is invisible to queries executed under tenant B.
- The service role can bypass RLS for migrations and admin tasks.
- Cross-tenant reads raise authorization errors, not data leakage.

These tests are stubs because a live PostgreSQL instance is required for full
enforcement verification. The SQLite test path is covered by
``test_rls_sqlite.py``.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Requires live PostgreSQL instance; stub for v3.11.5")
def test_postgres_rls_policies_installed():
    """Placeholder: verify RLS policies are present on core tables."""
    pass


@pytest.mark.skip(reason="Requires live PostgreSQL instance; stub for v3.11.5")
def test_postgres_tenant_a_cannot_read_tenant_b():
    """Placeholder: verify cross-tenant read isolation."""
    pass


@pytest.mark.skip(reason="Requires live PostgreSQL instance; stub for v3.11.5")
def test_postgres_service_role_bypasses_rls():
    """Placeholder: verify service role can bypass RLS for migrations."""
    pass
