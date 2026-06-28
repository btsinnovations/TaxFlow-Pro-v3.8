"""v3.11.6 expand RLS policies to all tenant-isolated tables

Revision ID: a7c3e9f2b1d4
Revises: f1a2b3c4d5e6
Create Date: 2026-06-27T20:00:00.000000

This migration expands PostgreSQL native RLS from the initial 3 tables
(accounts, statements, transactions) to all v3.11.6 tenant-isolated tables.
It also adds a service-role bypass for migrations and admin operations.

On SQLite this migration is a no-op.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f2b1d4'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All tenant-isolated tables that should have RLS policies.
TENANT_TABLES = [
    "coa_accounts",
    "gl_accounts",
    "categorization_rules",
    "general_ledger_entries",
    "flags",
    "depreciation_assets",
    "journals",
    "periods",
    "recurring_rules",
    "invoices",
    "loan_schedules",
    "investment_lots",
    "inventory_items",
    "inventory_transactions",
    "fx_rates",
    "reconciliation_imports",
    "reconciliation_matches",
    "budget_lines",
    "tax_line_mappings",
    "profile_memberships",
    "trained_models",
    # Original 3 tables already have RLS from b9f4e2c8d310, but we ensure
    # they still have policies (idempotent re-creation).
    "accounts",
    "statements",
    "transactions",
]


def upgrade() -> None:
    """Expand RLS to all tenant-isolated tables (PostgreSQL only)."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect != "postgresql":
        return

    # ------------------------------------------------------------------
    # 1. Create service-role bypass function
    # ------------------------------------------------------------------
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION taxflow.is_service_role()
        RETURNS boolean AS $$
        BEGIN
            RETURN current_setting('taxflow.service_role', true) = 'on';
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))
    op.execute(sa.text("""
        ALTER FUNCTION taxflow.is_service_role() SET search_path = taxflow, pg_catalog;
    """))

    # ------------------------------------------------------------------
    # 2. Enable + force RLS on all tenant tables
    # ------------------------------------------------------------------
    for table in TENANT_TABLES:
        # Skip tables that don't exist (idempotent)
        result = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
        ), {"t": table}).scalar()
        if not result:
            continue

        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        # Drop existing policy if present
        policy_name = f"{table}_tenant_isolation_policy"
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))

        # Create policy with service-role bypass using USING clause
        # tenant_id column must exist on the table for this to work
        col_check = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = 'tenant_id')"
        ), {"t": table}).scalar()

        if col_check:
            op.execute(sa.text(f"""
                CREATE POLICY {policy_name} ON {table}
                FOR ALL
                TO PUBLIC
                USING (
                    taxflow.is_service_role()
                    OR taxflow.tenant_id_matches(tenant_id)
                )
                WITH CHECK (
                    taxflow.is_service_role()
                    OR taxflow.tenant_id_matches(tenant_id)
                )
            """))
        else:
            # Tables without tenant_id (e.g., invoice_line_items, payments,
            # inventory_transactions) — skip RLS, they are scoped via parent FK
            pass

    # ------------------------------------------------------------------
    # 3. Update existing policies on original 3 tables to include bypass
    # ------------------------------------------------------------------
    for table in ["accounts", "statements", "transactions"]:
        policy_name = f"{table}_tenant_isolation_policy"
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        op.execute(sa.text(f"""
            CREATE POLICY {policy_name} ON {table}
            FOR ALL
            TO PUBLIC
            USING (
                taxflow.is_service_role()
                OR taxflow.tenant_id_matches(tenant_id)
            )
            WITH CHECK (
                taxflow.is_service_role()
                OR taxflow.tenant_id_matches(tenant_id)
            )
        """))


def downgrade() -> None:
    """Remove expanded RLS policies and service-role function."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect != "postgresql":
        return

    # Drop policies on all tenant tables
    for table in TENANT_TABLES:
        policy_name = f"{table}_tenant_isolation_policy"
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))

    # Re-create original 3-table policies without service-role bypass
    # (matching the b9f4e2c8d310 migration state)
    for table in ["accounts", "statements", "transactions"]:
        policy_name = f"{table}_tenant_isolation_policy"
        op.execute(sa.text(f"""
            CREATE POLICY {policy_name} ON {table}
            FOR ALL
            TO PUBLIC
            USING (taxflow.tenant_id_matches(tenant_id))
            WITH CHECK (taxflow.tenant_id_matches(tenant_id))
        """))

    # Drop service-role function
    op.execute(sa.text("DROP FUNCTION IF EXISTS taxflow.is_service_role()"))