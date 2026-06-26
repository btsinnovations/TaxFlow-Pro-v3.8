"""add fitid to transactions for OFX import deduplication

Revision ID: 330eb386b9c2
Revises: ba949088fd32
Create Date: 2026-06-25 10:07:35.568303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '330eb386b9c2'
down_revision: Union[str, Sequence[str], None] = 'e8f4a2c1d0b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # v3.11 adds OFX import support. Existing v3.10 deployments already have
    # the v3.11 bookkeeping module tables from prior model sync; this migration
    # only touches existing tables that need new columns.
    op.add_column('transactions', sa.Column('fitid', sa.String(), nullable=True))
    op.create_index(op.f('ix_transactions_fitid'), 'transactions', ['fitid'], unique=False)

    # gl_accounts gained an is_active flag for the COA module.
    op.add_column('gl_accounts', sa.Column('is_active', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_transactions_fitid'), table_name='transactions')
    op.drop_column('transactions', 'fitid')
    op.drop_column('gl_accounts', 'is_active')
