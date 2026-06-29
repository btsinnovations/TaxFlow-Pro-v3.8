"""add refresh_tokens table

Revision ID: f2a9b8c1d4e5
Revises: 2227f9254a8b
Create Date: 2026-06-21 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a9b8c1d4e5'
down_revision: Union[str, Sequence[str], None] = '2227f9254a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('family_id', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('replaced_by_token_hash', sa.String(length=64), nullable=True),
        sa.Column('client_hash', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_refresh_tokens_id'), 'refresh_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_family_id'), 'refresh_tokens', ['family_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    for idx_name in (
        op.f('ix_refresh_tokens_family_id'),
        op.f('ix_refresh_tokens_user_id'),
        op.f('ix_refresh_tokens_token_hash'),
        op.f('ix_refresh_tokens_id'),
    ):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {idx_name}"))
    conn.execute(sa.text("DROP TABLE IF EXISTS refresh_tokens"))
