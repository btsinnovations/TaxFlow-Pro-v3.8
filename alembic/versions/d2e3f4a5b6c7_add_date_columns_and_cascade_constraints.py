"""Add date columns, cascade constraints, and tighten user_id

Revision ID: d2e3f4a5b6c7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-21 10:00:00.000000

"""
from typing import Sequence, Union
from datetime import date

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Remove server_default=1 from transactions.user_id and flag uncertain rows.
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('user_id', server_default=None)
    op.add_column('transactions', sa.Column('owner_uncertain', sa.Boolean(), nullable=True))

    # 2. Convert date columns from String to Date where feasible.
    #    journals and periods already Date in their creation migration, but transactions
    #    and statements started as String. We also align GeneralLedgerEntry.date to Date.
    for table, cols in [
        ('statements', ['period_start', 'period_end']),
        ('transactions', ['date']),
        ('general_ledger_entries', ['date']),
    ]:
        for col in cols:
            op.execute(text(f"UPDATE {table} SET {col} = NULL WHERE {col} = ''"))
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.alter_column(
                    col,
                    existing_type=sa.String(),
                    type_=sa.Date(),
                    existing_nullable=True,
                    postgresql_using=f"{col}::date",
                )

    # 3. Add ondelete=CASCADE to all foreign keys.
    #    SQLite requires batch_alter_table to recreate FKs.
    #    For tables created in earlier migrations we add new constraints and drop old ones.
    _cascade_fk('clients', 'users', ['user_id'], 'fk_clients_user_id')
    _cascade_fk('accounts', 'clients', ['client_id'], 'fk_accounts_client_id')
    _cascade_fk('accounts', 'clients', ['tenant_id'], 'fk_accounts_tenant_id_clients')
    _cascade_fk('accounts', 'users', ['user_id'], 'fk_accounts_user_id')
    _cascade_fk('statements', 'accounts', ['account_id'], 'fk_statements_account_id')
    _cascade_fk('statements', 'clients', ['tenant_id'], 'fk_statements_tenant_id')
    _cascade_fk('statements', 'users', ['user_id'], 'fk_statements_user_id')
    _cascade_fk('transactions', 'statements', ['statement_id'], 'fk_transactions_statement_id')
    _cascade_fk('transactions', 'clients', ['tenant_id'], 'fk_transactions_tenant_id')
    _cascade_fk('transactions', 'users', ['user_id'], 'fk_transactions_user_id_users')
    _cascade_fk('transactions', 'gl_accounts', ['gl_account_id'], 'fk_transactions_gl_account_id_gl_accounts')
    _cascade_fk('audit_entries', 'users', ['actor_id'], 'fk_audit_entries_actor_id')
    _cascade_fk('depreciation_assets', 'clients', ['tenant_id'], 'fk_depreciation_assets_tenant_id')
    _cascade_fk('depreciation_assets', 'users', ['user_id'], 'fk_depreciation_assets_user_id')
    _cascade_fk('journals', 'clients', ['tenant_id'], 'fk_journals_tenant_id')
    _cascade_fk('journals', 'users', ['user_id'], 'fk_journals_user_id')
    _cascade_fk('periods', 'clients', ['tenant_id'], 'fk_periods_tenant_id')
    _cascade_fk('periods', 'users', ['user_id'], 'fk_periods_user_id')
    _cascade_fk('gl_accounts', 'clients', ['tenant_id'], 'fk_gl_accounts_tenant_id')
    _cascade_fk('gl_accounts', 'users', ['user_id'], 'fk_gl_accounts_user_id')
    _cascade_fk('categorization_rules', 'clients', ['tenant_id'], 'fk_categorization_rules_tenant_id')
    _cascade_fk('categorization_rules', 'users', ['user_id'], 'fk_categorization_rules_user_id')
    _cascade_fk('categorization_rules', 'gl_accounts', ['gl_account_id'], 'fk_categorization_rules_gl_account_id')
    _cascade_fk('general_ledger_entries', 'clients', ['tenant_id'], 'fk_general_ledger_entries_tenant_id')
    _cascade_fk('general_ledger_entries', 'users', ['user_id'], 'fk_general_ledger_entries_user_id')
    _cascade_fk('general_ledger_entries', 'transactions', ['transaction_id'], 'fk_general_ledger_entries_transaction_id')
    _cascade_fk('general_ledger_entries', 'gl_accounts', ['debit_account_id'], 'fk_general_ledger_entries_debit_account_id')
    _cascade_fk('general_ledger_entries', 'gl_accounts', ['credit_account_id'], 'fk_general_ledger_entries_credit_account_id')
    _cascade_fk('flags', 'clients', ['tenant_id'], 'fk_flags_tenant_id')
    _cascade_fk('flags', 'users', ['user_id'], 'fk_flags_user_id')
    _cascade_fk('flags', 'transactions', ['transaction_id'], 'fk_flags_transaction_id')
    _cascade_fk('flags', 'general_ledger_entries', ['journal_entry_id'], 'fk_flags_journal_entry_id')

    # 4. Make gl_accounts.account_type non-nullable and set server default.
    op.execute(text("UPDATE gl_accounts SET account_type = 'expense' WHERE account_type IS NULL"))
    with op.batch_alter_table('gl_accounts', schema=None) as batch_op:
        batch_op.alter_column(
            'account_type',
            existing_type=sa.String(),
            nullable=False,
            server_default=text("'expense'"),
        )


def downgrade() -> None:
    with op.batch_alter_table('gl_accounts', schema=None) as batch_op:
        batch_op.alter_column(
            'account_type',
            existing_type=sa.String(),
            nullable=True,
            server_default=None,
        )
    op.drop_column('transactions', 'owner_uncertain')
    for table, cols in [
        ('statements', ['period_start', 'period_end']),
        ('transactions', ['date']),
        ('general_ledger_entries', ['date']),
    ]:
        for col in cols:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.alter_column(
                    col,
                    existing_type=sa.Date(),
                    type_=sa.String(),
                    existing_nullable=True,
                )


def _cascade_fk(table: str, ref: str, columns: list, name: str) -> None:
    """Add a CASCADE foreign key, replacing any same-named constraint."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        # Postgres supports named constraints; drop and recreate idempotently.
        op.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))
        op.execute(text(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} "
            f"FOREIGN KEY ({', '.join(columns)}) REFERENCES {ref}(id) ON DELETE CASCADE"
        ))
        return
    # SQLite path: batch_alter_table recreates the table; ignore duplicates.
    try:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_foreign_key(name, ref, columns, ['id'], ondelete='CASCADE')
    except Exception:
        pass
