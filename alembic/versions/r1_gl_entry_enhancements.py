"""v3.11.6 R1: GL entry enhancements — entry_type, source_id, import_source, txn_uid

Revision ID: r1glentry
Revises: b3d4e5f6a7c8
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "r1glentry001"
down_revision = "b3d4e5f6a7c8"
branch_labels = None
depends_on = None


def _table_columns(table_name: str) -> set[str]:
    """Return the set of column names for the given table."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        try:
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            return {row[1] for row in rows}
        except Exception:
            return set()
    try:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table_name"
            ),
            {"table_name": table_name},
        ).fetchall()
        return {row[0] for row in rows}
    except Exception:
        return set()


def _index_exists(table_name: str, index_name: str) -> bool:
    """Check whether an index already exists on the given table."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        try:
            rows = conn.execute(text(f"PRAGMA index_list({table_name})")).fetchall()
            return any(row[1] == index_name for row in rows)
        except Exception:
            return False
    try:
        rows = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE tablename = :table_name "
                "AND indexname = :index_name"
            ),
            {"table_name": table_name, "index_name": index_name},
        ).fetchall()
        return bool(rows)
    except Exception:
        return False


def upgrade() -> None:
    cols = _table_columns('general_ledger_entries')
    if 'entry_type' not in cols:
        op.add_column("general_ledger_entries", sa.Column("entry_type", sa.String(), nullable=True, server_default="regular"))
    if 'source_id' not in cols:
        op.add_column("general_ledger_entries", sa.Column("source_id", sa.String(), nullable=True))
    if 'import_source' not in cols:
        op.add_column("general_ledger_entries", sa.Column("import_source", sa.String(), nullable=True))
    if 'txn_uid' not in cols:
        op.add_column("general_ledger_entries", sa.Column("txn_uid", sa.String(), nullable=True))

    if not _index_exists('general_ledger_entries', 'ix_general_ledger_entries_source_id'):
        op.create_index("ix_general_ledger_entries_source_id", "general_ledger_entries", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_general_ledger_entries_source_id", table_name="general_ledger_entries")
    op.drop_column("general_ledger_entries", "txn_uid")
    op.drop_column("general_ledger_entries", "import_source")
    op.drop_column("general_ledger_entries", "source_id")
    op.drop_column("general_ledger_entries", "entry_type")