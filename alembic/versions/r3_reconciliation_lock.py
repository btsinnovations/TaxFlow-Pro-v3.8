"""v3.11.6 R3: Reconciliation lock — is_completed, completed_at, completed_by_profile_id.

Revision ID: r3reconlock
Revises: r1glentry001
"""
from alembic import op
import sqlalchemy as sa

revision = "r3reconlock01"
down_revision = "r1glentry001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reconciliation_imports", sa.Column("is_completed", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    op.add_column("reconciliation_imports", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column("reconciliation_imports", sa.Column("completed_by_profile_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("reconciliation_imports", "completed_by_profile_id")
    op.drop_column("reconciliation_imports", "completed_at")
    op.drop_column("reconciliation_imports", "is_completed")