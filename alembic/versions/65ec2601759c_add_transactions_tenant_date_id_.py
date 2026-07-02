"""add transactions tenant date id composite index

Revision ID: 65ec2601759c
Revises: f98993328938
Create Date: 2026-07-01 22:18:24.351222

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65ec2601759c'
down_revision: Union[str, Sequence[str], None] = 'f98993328938'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    """Create the composite index used by keyset pagination."""
    if not _index_exists('transactions', 'ix_transactions_tenant_date_id'):
        op.create_index(
            'ix_transactions_tenant_date_id',
            'transactions',
            ['tenant_id', 'date', 'id'],
            unique=False,
        )


def downgrade() -> None:
    """Drop the composite index."""
    if _index_exists('transactions', 'ix_transactions_tenant_date_id'):
        op.drop_index('ix_transactions_tenant_date_id', table_name='transactions')
