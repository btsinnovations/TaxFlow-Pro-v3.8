"""add_pipeline_columns_to_transactions

Revision ID: 620568fedb26
Revises: 02e4db28bfaa
Create Date: 2026-06-17 22:45:54.878162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '620568fedb26'
down_revision: Union[str, Sequence[str], None] = '02e4db28bfaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transactions', sa.Column('split_id', sa.String(), nullable=True))
    op.add_column('transactions', sa.Column('parent_id', sa.String(), nullable=True))
    op.add_column('transactions', sa.Column('memo', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('graph_edges', sa.JSON(), nullable=True))
    op.create_index('ix_transactions_split_id', 'transactions', ['split_id'], unique=False)
    op.create_index('ix_transactions_parent_id', 'transactions', ['parent_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_transactions_parent_id', table_name='transactions')
    op.drop_index('ix_transactions_split_id', table_name='transactions')
    op.drop_column('transactions', 'graph_edges')
    op.drop_column('transactions', 'memo')
    op.drop_column('transactions', 'parent_id')
    op.drop_column('transactions', 'split_id')
