"""add audit entry Ed25519 signature column

Revision ID: 4f0bb0ee4bff
Revises: 842bfa1713f4
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f0bb0ee4bff'
down_revision: Union[str, Sequence[str], None] = '842bfa1713f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('audit_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signature', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('audit_entries', schema=None) as batch_op:
        batch_op.drop_column('signature')
