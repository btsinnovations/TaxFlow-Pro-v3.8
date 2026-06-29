"""add audit description and redaction support

Revision ID: 2227f9254a8b
Revises: 1116e8143fc6
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2227f9254a8b'
down_revision: Union[str, Sequence[str], None] = '1116e8143fc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    try:
        tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
    except Exception:
        tables = set()
    if 'audit_entries' not in tables:
        return
    with op.batch_alter_table('audit_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    try:
        tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
    except Exception:
        tables = set()
    if 'audit_entries' not in tables:
        return
    with op.batch_alter_table('audit_entries', schema=None) as batch_op:
        batch_op.drop_column('description')
