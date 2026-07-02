"""v3.11.6 R2: Period close — is_closed, closed_at, closed_by_profile_id on Period.

Revision ID: r2periodclose
Revises: r1glentry001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "r2periodclose01"
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
    cols = _table_columns('periods')
    if 'is_closed' not in cols:
        op.add_column("periods", sa.Column("is_closed", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    if 'closed_at' not in cols:
        op.add_column("periods", sa.Column("closed_at", sa.DateTime(), nullable=True))
    if 'closed_by_profile_id' not in cols:
        op.add_column("periods", sa.Column("closed_by_profile_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("periods", "closed_by_profile_id")
    op.drop_column("periods", "closed_at")
    op.drop_column("periods", "is_closed")