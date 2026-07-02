"""Add Stage 3 rules, flags, GL accounts, and workpaper refs

Revision ID: a1b2c3d4e5f6
Revises: 377bb18e5f7c
Create Date: 2026-06-20 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '377bb18e5f7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    """Check whether a table already exists in the target database."""
    return name in inspect(op.get_bind()).get_table_names()


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
    # GL accounts
    if not _table_exists('gl_accounts'):
        op.create_table(
            'gl_accounts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('account_type', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_gl_accounts_tenant_id', 'gl_accounts', ['tenant_id'], unique=False)
        op.create_index('ix_gl_accounts_id', 'gl_accounts', ['id'], unique=False)

    # General ledger entries
    if not _table_exists('general_ledger_entries'):
        op.create_table(
            'general_ledger_entries',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('transaction_id', sa.Integer(), nullable=True),
            sa.Column('date', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('debit_account_id', sa.Integer(), nullable=True),
            sa.Column('credit_account_id', sa.Integer(), nullable=True),
            sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column('memo', sa.String(), nullable=True),
            sa.Column('workpaper_ref', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
            sa.ForeignKeyConstraint(['debit_account_id'], ['gl_accounts.id'], ),
            sa.ForeignKeyConstraint(['credit_account_id'], ['gl_accounts.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_general_ledger_entries_tenant_id', 'general_ledger_entries', ['tenant_id'], unique=False)
        op.create_index('ix_general_ledger_entries_id', 'general_ledger_entries', ['id'], unique=False)

    # Categorization rules
    if not _table_exists('categorization_rules'):
        op.create_table(
            'categorization_rules',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('pattern', sa.String(), nullable=False),
            sa.Column('gl_account_id', sa.Integer(), nullable=False),
            sa.Column('priority', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('enabled', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['gl_account_id'], ['gl_accounts.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_categorization_rules_tenant_id', 'categorization_rules', ['tenant_id'], unique=False)
        op.create_index('ix_categorization_rules_id', 'categorization_rules', ['id'], unique=False)

    # Flags
    if not _table_exists('flags'):
        op.create_table(
            'flags',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('transaction_id', sa.Integer(), nullable=True),
            sa.Column('journal_entry_id', sa.Integer(), nullable=True),
            sa.Column('note', sa.String(), nullable=False),
            sa.Column('created_by', sa.String(), nullable=False),
            sa.Column('resolved', sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ),
            sa.ForeignKeyConstraint(['journal_entry_id'], ['general_ledger_entries.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_flags_tenant_id', 'flags', ['tenant_id'], unique=False)
        op.create_index('ix_flags_id', 'flags', ['id'], unique=False)

    # Add columns to existing tables (SQLite-compatible batch mode)
    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        with op.batch_alter_table('transactions', schema=None) as batch_op:
            if 'user_id' not in tx_cols:
                batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False, server_default=sa.text('1')))
            if 'gl_account_id' not in tx_cols:
                batch_op.add_column(sa.Column('gl_account_id', sa.Integer(), nullable=True))
            if 'workpaper_ref' not in tx_cols:
                batch_op.add_column(sa.Column('workpaper_ref', sa.String(), nullable=True))
            # SQLite batch mode recreates the table; only add FKs when the columns are present.
            batch_op.create_foreign_key(
                'fk_transactions_user_id_users',
                'users',
                ['user_id'], ['id']
            )
            batch_op.create_foreign_key(
                'fk_transactions_gl_account_id_gl_accounts',
                'gl_accounts',
                ['gl_account_id'], ['id']
            )


def downgrade() -> None:
    conn = op.get_bind()
    for tbl in ['transactions', 'flags', 'categorization_rules', 'general_ledger_entries', 'gl_accounts']:
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {tbl}"))
    for idx in [
        'ix_flags_id', 'ix_flags_tenant_id',
        'ix_categorization_rules_id', 'ix_categorization_rules_tenant_id',
        'ix_general_ledger_entries_id', 'ix_general_ledger_entries_tenant_id',
        'ix_gl_accounts_id', 'ix_gl_accounts_tenant_id',
    ]:
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {idx}"))
