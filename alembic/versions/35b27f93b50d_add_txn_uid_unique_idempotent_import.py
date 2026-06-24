"""add txn_uid unique idempotent import

Revision ID: 35b27f93b50d
Revises: 53e636150d46
Create Date: 2026-06-22 20:49:11.019663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35b27f93b50d'
down_revision: Union[str, Sequence[str], None] = '53e636150d46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add txn_uid column and unique index for idempotent imports."""
    # Idempotency UID for transactions. NULL allowed for legacy rows; new imports
    # always populate it. Unique together with tenant_id and user_id.
    op.add_column('transactions', sa.Column('txn_uid', sa.String(), nullable=True))
    op.create_index(
        op.f('ix_transactions_txn_uid'),
        'transactions',
        ['tenant_id', 'user_id', 'txn_uid'],
        unique=True,
    )


def downgrade() -> None:
    """Remove txn_uid idempotency support."""
    op.drop_index(op.f('ix_transactions_txn_uid'), table_name='transactions')
    op.drop_column('transactions', 'txn_uid')
