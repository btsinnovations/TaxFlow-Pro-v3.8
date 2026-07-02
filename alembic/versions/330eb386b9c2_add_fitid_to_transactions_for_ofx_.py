"""add fitid to transactions for OFX import deduplication

Revision ID: 330eb386b9c2
Revises: ba949088fd32
Create Date: 2026-06-25 10:07:35.568303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '330eb386b9c2'
down_revision: Union[str, Sequence[str], None] = 'e8f4a2c1d0b5'
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


def _index_exists(table_name: str, index_name: str) -> bool:
    """Check whether an index already exists on the given table."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        try:
            rows = conn.execute(text(f"PRAGMA index_list({table_name})")).fetchall()
            return any(row[1] == index_name for row in rows)
        except Exception:
            return False
    try:
        rows = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :table_name "
                "AND indexname = :index_name"
            ),
            {"table_name": table_name, "index_name": index_name},
        ).fetchall()
        return bool(rows)
    except Exception:
        return False


def upgrade() -> None:
    """Upgrade schema idempotently."""
    # v3.11 adds OFX import support. Existing v3.10 deployments already have
    # the v3.11 bookkeeping module tables from prior model sync; this migration
    # only touches existing tables that need new columns.
    tx_cols = _table_columns('transactions')
    if 'fitid' not in tx_cols:
        op.add_column('transactions', sa.Column('fitid', sa.String(), nullable=True))
    if not _index_exists('transactions', 'ix_transactions_fitid'):
        op.create_index(op.f('ix_transactions_fitid'), 'transactions', ['fitid'], unique=False)

    # gl_accounts gained an is_active flag for the COA module.
    gl_cols = _table_columns('gl_accounts')
    if 'is_active' not in gl_cols:
        op.add_column('gl_accounts', sa.Column('is_active', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_transactions_fitid'), table_name='transactions')
    op.drop_column('transactions', 'fitid')
    op.drop_column('gl_accounts', 'is_active')
