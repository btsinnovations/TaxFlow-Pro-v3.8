"""add audit entry Ed25519 signature column

Revision ID: 4f0bb0ee4bff
Revises: 842bfa1713f4
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '4f0bb0ee4bff'
down_revision: Union[str, Sequence[str], None] = '842bfa1713f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_columns(table_name: str) -> set:
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
    cols = _table_columns('audit_entries')
    if 'signature' not in cols:
        with op.batch_alter_table('audit_entries', schema=None) as batch_op:
            batch_op.add_column(sa.Column('signature', sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    try:
        with op.batch_alter_table('audit_entries', schema=None) as batch_op:
            batch_op.drop_column('signature')
    except Exception:
        # audit_entries may have been dropped by a later migration downgrade.
        pass
