"""add local auth columns to users

Revision ID: c3a1f7e9d220
Revises: b9f4e2c8d310
Create Date: 2026-06-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a1f7e9d220'
down_revision: Union[str, Sequence[str], None] = 'b9f4e2c8d310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('encryption_salt', sa.String(), nullable=True))
    op.add_column('users', sa.Column('keyfile_path', sa.String(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    try:
        tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
    except Exception:
        tables = set()
    if 'users' not in tables:
        return
    for col in ['keyfile_path', 'encryption_salt']:
        try:
            op.drop_column('users', col)
        except Exception:
            pass