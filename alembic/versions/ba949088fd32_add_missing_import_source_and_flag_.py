"""add missing import_source and flag columns

Revision ID: ba949088fd32
Revises: d9cf7c4a8fdf
Create Date: 2026-06-24 14:23:31.523067

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba949088fd32'
down_revision: Union[str, Sequence[str], None] = 'd9cf7c4a8fdf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_columns(table_name: str) -> set[str]:
    """Return the set of column names for the given table via SQLite introspection."""
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def upgrade() -> None:
    """Add columns that exist in the models but were not created by earlier migrations."""
    tx_cols = _table_columns('transactions')
    if 'import_source' not in tx_cols:
        op.add_column('transactions', sa.Column('import_source', sa.String(), nullable=True))

    flag_cols = _table_columns('flags')
    if 'created_by' not in flag_cols:
        op.add_column('flags', sa.Column('created_by', sa.String(), nullable=False, server_default='system'))
    if 'resolved_at' not in flag_cols:
        op.add_column('flags', sa.Column('resolved_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove columns added above."""
    flag_cols = _table_columns('flags')
    if 'resolved_at' in flag_cols:
        op.drop_column('flags', 'resolved_at')
    if 'created_by' in flag_cols:
        op.drop_column('flags', 'created_by')

    tx_cols = _table_columns('transactions')
    if 'import_source' in tx_cols:
        op.drop_column('transactions', 'import_source')
