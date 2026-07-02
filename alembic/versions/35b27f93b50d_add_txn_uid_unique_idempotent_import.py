"""add txn_uid unique idempotent import

Revision ID: 35b27f93b50d
Revises: 53e636150d46
Create Date: 2026-06-22 20:49:11.019663

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.exc import NoSuchTableError
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35b27f93b50d'
down_revision: Union[str, Sequence[str], None] = '53e636150d46'
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
    """Add txn_uid column and unique index for idempotent imports."""
    bind = op.get_bind()
    try:
        tables = inspect(bind).get_table_names()
    except Exception:
        tables = []
    if 'transactions' not in tables:
        return  # table may have been dropped by a later migration downgrade
    tx_cols = _table_columns('transactions')
    if 'txn_uid' not in tx_cols:
        op.add_column('transactions', sa.Column('txn_uid', sa.String(), nullable=True))
    if not _index_exists('transactions', 'ix_transactions_txn_uid'):
        op.create_index(
            op.f('ix_transactions_txn_uid'),
            'transactions',
            ['tenant_id', 'user_id', 'txn_uid'],
            unique=True,
        )


def downgrade() -> None:
    """Remove txn_uid idempotency support."""
    # The v3.11 baseline migration also creates this index/table, so when
    # downgrading through the baseline the table may already be gone. Be
    # defensive and skip if the table or index is absent.
    bind = op.get_bind()
    try:
        existing_indexes = {idx['name'] for idx in inspect(bind).get_indexes('transactions')}
    except NoSuchTableError:
        existing_indexes = set()
    if 'ix_transactions_txn_uid' in existing_indexes:
        op.drop_index(op.f('ix_transactions_txn_uid'), table_name='transactions')
    try:
        op.drop_column('transactions', 'txn_uid')
    except Exception:
        # Column may already be gone if the table was dropped by baseline downgrade.
        pass
