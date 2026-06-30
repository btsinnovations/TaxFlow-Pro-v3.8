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




def _table_exists(conn, table_name: str) -> bool:
    dialect = conn.dialect.name
    if dialect == "postgresql":
        result = conn.execute(
            sa.text("SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename=:t"),
            {"t": table_name},
        ).fetchone()
        return result is not None
    try:
        tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        return table_name in tables
    except Exception:
        return False

def downgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, 'users'):
        return
    for col in ['keyfile_path', 'encryption_salt']:
        try:
            op.drop_column('users', col)
        except Exception:
            pass