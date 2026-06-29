"""add categorization_rule form and line columns

Revision ID: 764988de938c
Revises: r5phasecops01
Create Date: 2026-06-29 19:19:06.344277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '764988de938c'
down_revision: Union[str, Sequence[str], None] = 'r5phasecops01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add form and line columns to categorization_rules."""
    op.add_column('categorization_rules', sa.Column('form', sa.String(), nullable=True))
    op.add_column('categorization_rules', sa.Column('line', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove form and line columns from categorization_rules."""
    op.drop_column('categorization_rules', 'line')
    op.drop_column('categorization_rules', 'form')
