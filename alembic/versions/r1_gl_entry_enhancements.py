"""v3.11.6 R1: GL entry enhancements — entry_type, source_id, import_source, txn_uid

Revision ID: r1glentry
Revises: b3d4e5f6a7c8
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = "r1glentry001"
down_revision = "b3d4e5f6a7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add entry_type column with default 'regular'
    op.add_column("general_ledger_entries", sa.Column("entry_type", sa.String(), nullable=True, server_default="regular"))
    # Add source_id column (e.g., "txn:42", "import:5", "recurring:3")
    op.add_column("general_ledger_entries", sa.Column("source_id", sa.String(), nullable=True))
    # Add import_source column (copied from Transaction.import_source)
    op.add_column("general_ledger_entries", sa.Column("import_source", sa.String(), nullable=True))
    # Add txn_uid column for idempotency
    op.add_column("general_ledger_entries", sa.Column("txn_uid", sa.String(), nullable=True))

    # Create index on source_id for fast idempotency checks
    op.create_index("ix_general_ledger_entries_source_id", "general_ledger_entries", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_general_ledger_entries_source_id", table_name="general_ledger_entries")
    op.drop_column("general_ledger_entries", "txn_uid")
    op.drop_column("general_ledger_entries", "import_source")
    op.drop_column("general_ledger_entries", "source_id")
    op.drop_column("general_ledger_entries", "entry_type")