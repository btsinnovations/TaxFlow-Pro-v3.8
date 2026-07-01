"""fix periods start_date end_date to date type

Revision ID: f98993328938
Revises: 764988de938c
Create Date: 2026-07-01 08:59:54.450677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f98993328938'
down_revision: Union[str, Sequence[str], None] = '764988de938c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure periods.start_date and periods.end_date are DATE columns.

    Migration e8b7c1d5f3a2 incorrectly created these as sa.String() on
    PostgreSQL. Later migrations only create the table when absent, so the
    wrong type persisted. This migration fixes existing deployments without
    affecting SQLite, which already uses Date.
    """
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.alter_column(
            "periods",
            "start_date",
            existing_type=sa.String(),
            type_=sa.Date(),
            postgresql_using="start_date::date",
        )
        op.alter_column(
            "periods",
            "end_date",
            existing_type=sa.String(),
            type_=sa.Date(),
            postgresql_using="end_date::date",
        )


def downgrade() -> None:
    """Revert periods.start_date and periods.end_date back to String."""
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        op.alter_column(
            "periods",
            "start_date",
            existing_type=sa.Date(),
            type_=sa.String(),
        )
        op.alter_column(
            "periods",
            "end_date",
            existing_type=sa.Date(),
            type_=sa.String(),
        )
