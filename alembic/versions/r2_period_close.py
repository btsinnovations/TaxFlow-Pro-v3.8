"""v3.11.6 R2: Period close — is_closed, closed_at, closed_by_profile_id on Period.

Revision ID: r2periodclose
Revises: r1glentry001
"""
from alembic import op
import sqlalchemy as sa

revision = "r2periodclose01"
down_revision = "r1glentry001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("periods", sa.Column("is_closed", sa.Boolean(), nullable=True, server_default=sa.text("0")))
    op.add_column("periods", sa.Column("closed_at", sa.DateTime(), nullable=True))
    op.add_column("periods", sa.Column("closed_by_profile_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("periods", "closed_by_profile_id")
    op.drop_column("periods", "closed_at")
    op.drop_column("periods", "is_closed")