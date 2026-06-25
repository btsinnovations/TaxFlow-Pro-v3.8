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


def upgrade() -> None:
    """Add columns that exist in the models but were not created by earlier migrations."""
    # transactions.import_source
    if not op.get_bind().dialect.has_column(op.get_bind(), 'transactions', 'import_source'):
        op.add_column('transactions', sa.Column('import_source', sa.String(), nullable=True))

    # flags.created_by and flags.resolved_at
    if not op.get_bind().dialect.has_column(op.get_bind(), 'flags', 'created_by'):
        op.add_column('flags', sa.Column('created_by', sa.String(), nullable=False, server_default='system'))
    if not op.get_bind().dialect.has_column(op.get_bind(), 'flags', 'resolved_at'):
        op.add_column('flags', sa.Column('resolved_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove columns added above."""
    if op.get_bind().dialect.has_column(op.get_bind(), 'flags', 'resolved_at'):
        op.drop_column('flags', 'resolved_at')
    if op.get_bind().dialect.has_column(op.get_bind(), 'flags', 'created_by'):
        op.drop_column('flags', 'created_by')
    if op.get_bind().dialect.has_column(op.get_bind(), 'transactions', 'import_source'):
        op.drop_column('transactions', 'import_source')
