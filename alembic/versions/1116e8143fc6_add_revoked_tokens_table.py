"""add revoked_tokens table

Revision ID: 1116e8143fc6
Revises: d2e3f4a5b6c7
Create Date: 2026-06-20 13:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1116e8143fc6'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('token_type', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti')
    )
    op.create_index(op.f('ix_revoked_tokens_id'), 'revoked_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_revoked_tokens_jti'), 'revoked_tokens', ['jti'], unique=True)
    op.create_index(op.f('ix_revoked_tokens_user_id'), 'revoked_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    for idx_name in (
        op.f('ix_revoked_tokens_user_id'),
        op.f('ix_revoked_tokens_jti'),
        op.f('ix_revoked_tokens_id'),
    ):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {idx_name}"))
    conn.execute(sa.text("DROP TABLE IF EXISTS revoked_tokens"))
