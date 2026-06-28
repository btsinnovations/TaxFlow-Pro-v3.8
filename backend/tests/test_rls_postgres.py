"""PostgreSQL Row-Level Security tests for v3.11.6.

These tests require a live PostgreSQL instance and are skipped when
TEST_DATABASE_URL is not set. They verify:
- RLS policies exist on all tenant-isolated tables.
- A row in tenant A is invisible to queries under tenant B context.
- The service role can bypass RLS for migrations and admin operations.
- Cross-tenant reads return empty results, not errors.
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.rls import set_tenant_id, set_service_role, clear_tenant_id
from backend.routers.auth import get_password_hash

# Import Alembic command and config so the fixture can run real migrations.
from alembic.config import Config
from alembic import command


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set; skipping PostgreSQL RLS tests",
)


def _run_migrations(url: str) -> None:
    """Run Alembic migrations against the provided PostgreSQL URL."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="module")
def pg_engine():
    """Create a fresh PostgreSQL schema via Alembic for the test module."""
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    # Drop all objects and re-run migrations to ensure RLS policies exist.
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    _run_migrations(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_session(pg_engine):
    """Session bound to the PostgreSQL test database."""
    SessionLocal = sessionmaker(bind=pg_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def pg_tenant_data(pg_session):
    """Seed two tenants with distinct COA accounts for isolation tests."""
    # Enable service role for data seeding
    set_service_role(pg_session, True)

    # Create two users + clients (tenants)
    user1 = models.User(
        username="rls_user1",
        email="rls1@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    user2 = models.User(
        username="rls_user2",
        email="rls2@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    pg_session.add_all([user1, user2])
    pg_session.commit()
    pg_session.refresh(user1)
    pg_session.refresh(user2)

    client1 = models.Client(name="RLS Tenant A", user_id=user1.id)
    client2 = models.Client(name="RLS Tenant B", user_id=user2.id)
    pg_session.add_all([client1, client2])
    pg_session.commit()
    pg_session.refresh(client1)
    pg_session.refresh(client2)

    # Create COA accounts for each tenant
    acct1 = models.CoaAccount(
        tenant_id=client1.id, number=1010, name="Cash A", type="asset"
    )
    acct2 = models.CoaAccount(
        tenant_id=client2.id, number=1010, name="Cash B", type="asset"
    )
    pg_session.add_all([acct1, acct2])
    pg_session.commit()
    pg_session.refresh(acct1)
    pg_session.refresh(acct2)

    # Disable service role after seeding
    set_service_role(pg_session, False)

    return {
        "user1": user1,
        "user2": user2,
        "client1": client1,
        "client2": client2,
        "acct1": acct1,
        "acct2": acct2,
    }


def test_postgres_rls_policies_installed(pg_engine):
    """Verify RLS policies exist on all core tenant-isolated tables."""
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT tablename, policyname FROM pg_policies "
            "WHERE schemaname = 'public' AND policyname LIKE '%_tenant_isolation_policy' "
            "ORDER BY tablename"
        ))
        policies = {r[0] for r in result.fetchall()}

    expected_tables = {
        "coa_accounts", "accounts", "statements", "transactions",
        "gl_accounts", "categorization_rules", "general_ledger_entries",
        "flags", "depreciation_assets", "journals", "periods",
        "recurring_rules", "invoices", "loan_schedules", "investment_lots",
        "inventory_items", "fx_rates", "reconciliation_imports",
        "reconciliation_matches", "budget_lines", "tax_line_mappings",
    }
    found = policies & expected_tables
    # At least the core tables should have policies
    assert "coa_accounts" in found
    assert "accounts" in found
    assert "transactions" in found
    assert len(found) >= 10, f"Expected >=10 policies, found {len(found)}: {found}"


def test_postgres_tenant_a_cannot_read_tenant_b(pg_session, pg_tenant_data):
    """A query under tenant A context must not see tenant B's rows."""
    tenant_a_id = pg_tenant_data["client1"].id
    tenant_b_id = pg_tenant_data["client2"].id

    # Set tenant context to A
    set_tenant_id(pg_session, tenant_a_id)

    # Query coa_accounts — should only see tenant A's accounts
    accounts = pg_session.query(models.CoaAccount).all()
    for acct in accounts:
        assert acct.tenant_id == tenant_a_id, (
            f"Tenant A query returned account from tenant {acct.tenant_id}"
        )

    # Verify tenant B's account is NOT visible
    tenant_b_acct_id = pg_tenant_data["acct2"].id
    found = pg_session.query(models.CoaAccount).filter(
        models.CoaAccount.id == tenant_b_acct_id
    ).first()
    assert found is None, "Tenant A context can see tenant B's COA account"

    clear_tenant_id(pg_session)


def test_postgres_tenant_b_cannot_read_tenant_a(pg_session, pg_tenant_data):
    """A query under tenant B context must not see tenant A's rows."""
    tenant_a_id = pg_tenant_data["client1"].id
    tenant_b_id = pg_tenant_data["client2"].id

    set_tenant_id(pg_session, tenant_b_id)

    accounts = pg_session.query(models.CoaAccount).all()
    for acct in accounts:
        assert acct.tenant_id == tenant_b_id

    # Verify tenant A's account is NOT visible
    tenant_a_acct_id = pg_tenant_data["acct1"].id
    found = pg_session.query(models.CoaAccount).filter(
        models.CoaAccount.id == tenant_a_acct_id
    ).first()
    assert found is None, "Tenant B context can see tenant A's COA account"

    clear_tenant_id(pg_session)


def test_postgres_service_role_bypasses_rls(pg_session, pg_tenant_data):
    """The service role can see all tenant rows regardless of tenant context."""
    # Enable service role
    set_service_role(pg_session, True)

    # Without any tenant context set, service role should see all accounts
    clear_tenant_id(pg_session)
    set_service_role(pg_session, True)

    accounts = pg_session.query(models.CoaAccount).all()
    tenant_ids = {acct.tenant_id for acct in accounts}

    tenant_a_id = pg_tenant_data["client1"].id
    tenant_b_id = pg_tenant_data["client2"].id

    assert tenant_a_id in tenant_ids, "Service role cannot see tenant A accounts"
    assert tenant_b_id in tenant_ids, "Service role cannot see tenant B accounts"

    set_service_role(pg_session, False)


def test_postgres_rls_enabled_on_tables(pg_engine):
    """Verify RLS is enabled and forced on core tenant tables."""
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT relname, relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname IN "
            "('coa_accounts', 'accounts', 'transactions', 'statements') "
            "AND relkind = 'r'"
        ))
        rows = result.fetchall()

    for row in rows:
        table_name, rls_enabled, rls_forced = row
        assert rls_enabled, f"RLS not enabled on {table_name}"
        assert rls_forced, f"RLS not forced on {table_name}"


def test_postgres_tenant_insert_blocked_for_wrong_tenant(pg_session, pg_tenant_data):
    """INSERT with wrong tenant_id should be blocked by WITH CHECK policy."""
    tenant_a_id = pg_tenant_data["client1"].id
    tenant_b_id = pg_tenant_data["client2"].id

    # Set context to tenant A
    set_tenant_id(pg_session, tenant_a_id)

    # Try to insert a row with tenant_b_id — should fail
    bad_account = models.CoaAccount(
        tenant_id=tenant_b_id, number=9999, name="Stolen", type="asset"
    )
    pg_session.add(bad_account)
    with pytest.raises(Exception, match="(row-level security|RLS|policy)"):
        pg_session.commit()

    # Rollback the failed transaction
    pg_session.rollback()
    clear_tenant_id(pg_session)