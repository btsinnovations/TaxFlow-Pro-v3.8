"""enable postgresql row level security

Revision ID: b9f4e2c8d310
Revises: d75a7eba9fd0
Create Date: 2026-06-14 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'b9f4e2c8d310'
down_revision: Union[str, Sequence[str], None] = 'd75a7eba9fd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable RLS on tenant-isolated tables (PostgreSQL only)."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect != "postgresql":
        # SQLite does not support RLS; this migration is a no-op there.
        return

    # Ensure tenants only see their own rows when a tenant context is set.
    tables = ["accounts", "statements", "transactions"]
    for table in tables:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    # Helper function for stable tenant comparison.
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION taxflow.tenant_id_matches(integer)
        RETURNS boolean AS $$
        BEGIN
            RETURN $1::text = current_setting('taxflow.tenant_id', true);
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))

    for table in tables:
        policy_name = f"{table}_tenant_isolation_policy"
        # Drop existing policy if present to make this migration idempotent.
        op.execute(sa.text(
            f"DROP POLICY IF EXISTS {policy_name} ON {table}"
        ))
        op.execute(sa.text(f"""
            CREATE POLICY {policy_name} ON {table}
            FOR ALL
            TO PUBLIC
            USING (taxflow.tenant_id_matches(tenant_id))
            WITH CHECK (taxflow.tenant_id_matches(tenant_id))
        """))

    # Bypass policy for superusers is implicit; ensure the taxflow schema exists.
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS taxflow"))
    op.execute(sa.text("""
        ALTER FUNCTION taxflow.tenant_id_matches(integer) SET search_path = taxflow, pg_catalog;
    """))


def downgrade() -> None:
    """Remove RLS policies and helper function."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect != "postgresql":
        return

    for table in ["accounts", "statements", "transactions"]:
        policy_name = f"{table}_tenant_isolation_policy"
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    op.execute(sa.text("DROP FUNCTION IF EXISTS taxflow.tenant_id_matches(integer)"))
