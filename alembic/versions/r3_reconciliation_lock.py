"""v3.11.6 R3: Reconciliation lock — is_completed, completed_at, completed_by_profile_id.

Revision ID: r3reconlock
Revises: r1glentry001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "r3reconlock01"
down_revision = "r1glentry001"
branch_labels = None
depends_on = None


def _table_columns(table_name: str) -> set[str]:
    """Return the set of column names for the given table."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        try:
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            return {row[1] for row in rows}
        except Exception:
            return set()
    try:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table_name"
            ),
            {"table_name": table_name},
        ).fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def upgrade() -> None:
    cols = _table_columns('reconciliation_imports')
    if 'is_completed' not in cols:
        op.add_column("reconciliation_imports", sa.Column("is_completed", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    if 'completed_at' not in cols:
        op.add_column("reconciliation_imports", sa.Column("completed_at", sa.DateTime(), nullable=True))
    if 'completed_by_profile_id' not in cols:
        op.add_column("reconciliation_imports", sa.Column("completed_by_profile_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("reconciliation_imports", "completed_by_profile_id")
    op.drop_column("reconciliation_imports", "completed_at")
    op.drop_column("reconciliation_imports", "is_completed")