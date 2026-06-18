"""add_ml_enabled_to_firm_settings

Revision ID: 02e4db28bfaa
Revises: d624428edb28
Create Date: 2026-06-17 22:45:54.019392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02e4db28bfaa'
down_revision: Union[str, Sequence[str], None] = 'd624428edb28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('firm_settings', sa.Column('ml_enabled', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('firm_settings', 'ml_enabled')
