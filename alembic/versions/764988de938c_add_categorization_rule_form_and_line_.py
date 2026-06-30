"""add categorization_rule form and line columns

Revision ID: 764988de938c
Revises: r5phasecops01
Create Date: 2026-06-29 19:19:06.344277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


def _table_columns(table_name: str) -> set[str]:
    """Return the set of column names for the given table."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        rows = conn.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
        return {row[1] for row in rows}
    rows = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table_name"
        ),
        {"table_name": table_name},
    ).fetchall()
    return {row[0] for row in rows}


# revision identifiers, used by Alembic.
revision: str = '764988de938c'
down_revision: Union[str, Sequence[str], None] = 'r5phasecops01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add form and line columns to categorization_rules (idempotent)."""
    cols = _table_columns('categorization_rules')
    if 'form' not in cols:
        op.add_column('categorization_rules', sa.Column('form', sa.String(), nullable=True))
    if 'line' not in cols:
        op.add_column('categorization_rules', sa.Column('line', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove form and line columns from categorization_rules (idempotent)."""
    cols = _table_columns('categorization_rules')
    if 'line' in cols:
        op.drop_column('categorization_rules', 'line')
    if 'form' in cols:
        op.drop_column('categorization_rules', 'form')
