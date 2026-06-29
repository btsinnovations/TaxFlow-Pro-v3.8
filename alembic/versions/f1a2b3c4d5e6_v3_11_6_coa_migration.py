"""v3.11.6 COA migration: coa_accounts table + missing v3.11 tables

Revision ID: f1a2b3c4d5e6
Revises: e8f4a2c1d0b5
Create Date: 2026-06-27T16:30:00.000000

This migration:
1. Creates the ``coa_accounts`` table with hierarchical support (parent_id),
   integer account numbers, and the five canonical account types.
2. Migrates existing ``gl_accounts`` rows into ``coa_accounts`` with integer
   numbers assigned by the locked numbering scheme:
     Assets: 1000-1999, Liabilities: 2000-2999, Equity: 3000-3999,
     Revenue: 4000-4999, Expenses: 5000-9999
3. Adds ``coa_account_id`` columns to tables that previously referenced
   ``gl_accounts.id`` (transactions, general_ledger_entries,
   categorization_rules).
4. Creates all missing v3.11 tables not covered by earlier migrations.
5. Reversible: downgrade drops new columns and tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '330eb386b9c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    """Check whether a table already exists in the target database."""
    return name in inspect(op.get_bind()).get_table_names()


def _table_columns(table_name: str) -> set:
    """Return the set of column names for the given table.

    Portable across SQLite (PRAGMA) and PostgreSQL (information_schema).
    """
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        try:
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            return {row[1] for row in rows}
        except Exception:
            return set()
    # PostgreSQL information_schema path
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


def _type_to_number_range(account_type: str) -> tuple[int, int]:
    """Map an account type string to its number range."""
    mapping = {
        "asset": (1000, 1999),
        "liability": (2000, 2999),
        "equity": (3000, 3999),
        "income": (4000, 4999),
        "revenue": (4000, 4999),
        "expense": (5000, 9999),
    }
    return mapping.get(account_type.lower().strip(), (5000, 9999))


def _normalize_type(account_type: str) -> str:
    """Normalize account type to the five canonical types."""
    lowered = account_type.lower().strip()
    if lowered in ("income", "revenue"):
        return "income"
    if lowered in ("asset", "liability", "equity", "expense"):
        return lowered
    return "expense"


def upgrade() -> None:
    """Create coa_accounts, migrate data, add missing v3.11 tables."""
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Create coa_accounts table
    # ------------------------------------------------------------------
    if not _table_exists('coa_accounts'):
        op.create_table(
            'coa_accounts',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('parent_id', sa.Integer(),
                      sa.ForeignKey('coa_accounts.id', ondelete='SET NULL'),
                      nullable=True),
            sa.Column('number', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('type', sa.String(), nullable=False, default='expense'),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_coa_accounts_tenant_id', 'coa_accounts', ['tenant_id'])
        op.create_index('ix_coa_accounts_tenant_number', 'coa_accounts',
                        ['tenant_id', 'number'], unique=True)
        op.create_index('ix_coa_accounts_parent_id', 'coa_accounts', ['parent_id'])

    # ------------------------------------------------------------------
    # 2. Migrate gl_accounts data into coa_accounts
    # ------------------------------------------------------------------
    if _table_exists('gl_accounts'):
        conn = bind
        # Fetch all gl_accounts ordered by id for deterministic migration
        rows = conn.execute(text(
            "SELECT id, tenant_id, code, name, account_type, is_active, created_at "
            "FROM gl_accounts ORDER BY id"
        )).fetchall()

        # Group by tenant + type to assign sequential numbers within each range
        tenant_type_counters: dict[tuple[int, str], int] = {}
        gl_id_to_coa_id: dict[int, int] = {}

        for row in rows:
            gl_id, tenant_id, code, name, account_type, is_active, created_at = row
            normalized = _normalize_type(account_type or "expense")
            base, _top = _type_to_number_range(normalized)
            key = (tenant_id, normalized)
            counter = tenant_type_counters.get(key, base)
            tenant_type_counters[key] = counter + 1

            # Try to use the existing code as the number if it's numeric and in range
            try:
                code_int = int(str(code).strip())
                if base <= code_int <= _type_to_number_range(normalized)[1]:
                    # Use the code's integer value, but ensure uniqueness
                    if not any(
                        v == code_int for k, v in tenant_type_counters.items()
                        if k[0] == tenant_id
                    ):
                        number = code_int
                        tenant_type_counters[key] = code_int + 1
                    else:
                        number = counter
                        tenant_type_counters[key] = counter + 1
                else:
                    number = counter
                    tenant_type_counters[key] = counter + 1
            except (ValueError, TypeError):
                number = counter
                tenant_type_counters[key] = counter + 1

            # Insert into coa_accounts and capture the new id.
            dialect = conn.dialect.name
            if dialect == "sqlite":
                conn.execute(text(
                    "INSERT INTO coa_accounts (tenant_id, parent_id, number, name, type, is_active, created_at, updated_at) "
                    "VALUES (:tenant_id, NULL, :number, :name, :type, :is_active, :created_at, :created_at)"
                ), {
                    "tenant_id": tenant_id,
                    "number": number,
                    "name": name,
                    "type": normalized,
                    "is_active": is_active if is_active is not None else 1,
                    "created_at": created_at,
                })
                new_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            else:
                new_id = conn.execute(text(
                    "INSERT INTO coa_accounts (tenant_id, parent_id, number, name, type, is_active, created_at, updated_at) "
                    "VALUES (:tenant_id, NULL, :number, :name, :type, :is_active, :created_at, :created_at) "
                    "RETURNING id"
                ), {
                    "tenant_id": tenant_id,
                    "number": number,
                    "name": name,
                    "type": normalized,
                    "is_active": is_active if is_active is not None else 1,
                    "created_at": created_at,
                }).scalar()
            gl_id_to_coa_id[gl_id] = new_id

    # ------------------------------------------------------------------
    # 3. Add coa_account_id columns to related tables
    # ------------------------------------------------------------------
    # Use batch_alter_table for SQLite compatibility (SQLite doesn't support
    # ALTER TABLE ADD CONSTRAINT; batch mode recreates the table with the
    # new column + FK in a single copy-and-move operation).
    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        if 'coa_account_id' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(
                    sa.Column('coa_account_id', sa.Integer(), nullable=True))

    if _table_exists('general_ledger_entries'):
        gl_cols = _table_columns('general_ledger_entries')
        if 'debit_coa_account_id' not in gl_cols:
            with op.batch_alter_table('general_ledger_entries') as batch_op:
                batch_op.add_column(
                    sa.Column('debit_coa_account_id', sa.Integer(), nullable=True))
        if 'credit_coa_account_id' not in gl_cols:
            with op.batch_alter_table('general_ledger_entries') as batch_op:
                batch_op.add_column(
                    sa.Column('credit_coa_account_id', sa.Integer(), nullable=True))

    if _table_exists('categorization_rules'):
        cr_cols = _table_columns('categorization_rules')
        if 'coa_account_id' not in cr_cols:
            with op.batch_alter_table('categorization_rules') as batch_op:
                batch_op.add_column(
                    sa.Column('coa_account_id', sa.Integer(), nullable=True))

    # ------------------------------------------------------------------
    # 4. Create missing v3.11 tables (idempotent)
    # ------------------------------------------------------------------

    # -- profile_memberships
    if not _table_exists('profile_memberships'):
        op.create_table(
            'profile_memberships',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('profile_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('role', sa.String(), nullable=False, default='viewer'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_profile_memberships_profile_id', 'profile_memberships', ['profile_id'])
        op.create_index('ix_profile_memberships_user_id', 'profile_memberships', ['user_id'])

    # -- depreciation_assets
    if not _table_exists('depreciation_assets'):
        op.create_table(
            'depreciation_assets',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('asset_class', sa.String(), nullable=False),
            sa.Column('cost_basis', sa.Numeric(14, 2), nullable=False),
            sa.Column('placed_in_service_date', sa.Date(), nullable=False),
            sa.Column('recovery_period_years', sa.Integer(), nullable=False),
            sa.Column('method', sa.String(), nullable=False, default='MACRS-GDS'),
            sa.Column('convention', sa.String(), nullable=False, default='HY'),
            sa.Column('section_179', sa.Numeric(14, 2), nullable=False, default=0),
            sa.Column('bonus_depreciation', sa.Numeric(14, 2), nullable=False, default=0),
            sa.Column('salvage_value', sa.Numeric(14, 2), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_depreciation_assets_tenant_id', 'depreciation_assets', ['tenant_id'])
        op.create_index('ix_depreciation_assets_user_id', 'depreciation_assets', ['user_id'])

    # -- journals
    if not _table_exists('journals'):
        op.create_table(
            'journals',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('memo', sa.String(), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_journals_tenant_id', 'journals', ['tenant_id'])
        op.create_index('ix_journals_user_id', 'journals', ['user_id'])

    # -- periods
    if not _table_exists('periods'):
        op.create_table(
            'periods',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_periods_tenant_id', 'periods', ['tenant_id'])
        op.create_index('ix_periods_user_id', 'periods', ['user_id'])

    # -- general_ledger_entries
    if not _table_exists('general_ledger_entries'):
        op.create_table(
            'general_ledger_entries',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('transaction_id', sa.Integer(),
                      sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=True),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('debit_account_id', sa.Integer(),
                      sa.ForeignKey('gl_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('credit_account_id', sa.Integer(),
                      sa.ForeignKey('gl_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('debit_coa_account_id', sa.Integer(),
                      sa.ForeignKey('coa_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('credit_coa_account_id', sa.Integer(),
                      sa.ForeignKey('coa_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('memo', sa.String(), nullable=True),
            sa.Column('workpaper_ref', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_general_ledger_entries_tenant_id',
                        'general_ledger_entries', ['tenant_id'])

    # -- flags
    if not _table_exists('flags'):
        op.create_table(
            'flags',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('transaction_id', sa.Integer(),
                      sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=True),
            sa.Column('journal_entry_id', sa.Integer(),
                      sa.ForeignKey('general_ledger_entries.id', ondelete='CASCADE'),
                      nullable=True),
            sa.Column('note', sa.String(), nullable=False),
            sa.Column('created_by', sa.String(), nullable=False, server_default='system'),
            sa.Column('resolved', sa.Boolean(), default=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_flags_tenant_id', 'flags', ['tenant_id'])

    # -- invoices
    if not _table_exists('invoices'):
        op.create_table(
            'invoices',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('contact_name', sa.String(), nullable=False),
            sa.Column('invoice_number', sa.String(), nullable=False),
            sa.Column('issue_date', sa.Date(), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=False),
            sa.Column('total', sa.Numeric(12, 2), nullable=False, default=0),
            sa.Column('amount_paid', sa.Numeric(12, 2), nullable=False, default=0),
            sa.Column('status', sa.String(), nullable=False, default='open'),
            sa.Column('is_bill', sa.Boolean(), default=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- invoice_line_items
    if not _table_exists('invoice_line_items'):
        op.create_table(
            'invoice_line_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('invoice_id', sa.Integer(),
                      sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
            sa.Column('description', sa.String(), nullable=False),
            sa.Column('qty', sa.Numeric(12, 4), nullable=False, default=1),
            sa.Column('rate', sa.Numeric(12, 4), nullable=False, default=0),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False, default=0),
        )

    # -- payments
    if not _table_exists('payments'):
        op.create_table(
            'payments',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('invoice_id', sa.Integer(),
                      sa.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('method', sa.String(), nullable=False, default='manual'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- loan_schedules
    if not _table_exists('loan_schedules'):
        op.create_table(
            'loan_schedules',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('original_principal', sa.Numeric(14, 2), nullable=False),
            sa.Column('rate', sa.Numeric(6, 4), nullable=False),
            sa.Column('term_months', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('payment_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('schedule_json', sa.String(), default='[]'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- investment_lots
    if not _table_exists('investment_lots'):
        op.create_table(
            'investment_lots',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('symbol', sa.String(), nullable=False),
            sa.Column('shares', sa.Numeric(14, 6), nullable=False),
            sa.Column('cost_basis', sa.Numeric(14, 4), nullable=False),
            sa.Column('acquisition_date', sa.Date(), nullable=False),
            sa.Column('sale_date', sa.Date(), nullable=True),
            sa.Column('sale_proceeds', sa.Numeric(14, 4), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- inventory_items
    if not _table_exists('inventory_items'):
        op.create_table(
            'inventory_items',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('sku', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('cogs_account_id', sa.Integer(),
                      sa.ForeignKey('gl_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('income_account_id', sa.Integer(),
                      sa.ForeignKey('gl_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('asset_account_id', sa.Integer(),
                      sa.ForeignKey('gl_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('valuation_method', sa.String(), nullable=False, default='average'),
            sa.Column('qty_on_hand', sa.Numeric(12, 4), nullable=False, default=0),
            sa.Column('unit_cost', sa.Numeric(12, 4), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- inventory_transactions
    if not _table_exists('inventory_transactions'):
        op.create_table(
            'inventory_transactions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('item_id', sa.Integer(),
                      sa.ForeignKey('inventory_items.id', ondelete='CASCADE'), nullable=False),
            sa.Column('qty', sa.Numeric(12, 4), nullable=False),
            sa.Column('unit_cost', sa.Numeric(12, 4), nullable=False),
            sa.Column('total_cost', sa.Numeric(12, 2), nullable=False),
            sa.Column('type', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- fx_rates
    if not _table_exists('fx_rates'):
        op.create_table(
            'fx_rates',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('from_currency', sa.String(), nullable=False),
            sa.Column('to_currency', sa.String(), nullable=False),
            sa.Column('rate', sa.Numeric(18, 8), nullable=False),
            sa.Column('effective_date', sa.Date(), nullable=False),
            sa.Column('source', sa.String(), nullable=False, default='manual'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- reconciliation_imports
    if not _table_exists('reconciliation_imports'):
        op.create_table(
            'reconciliation_imports',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('import_date', sa.Date(), nullable=False),
            sa.Column('statement_date', sa.Date(), nullable=True),
            sa.Column('statement_balance', sa.Numeric(12, 2), nullable=False),
            sa.Column('filename', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- reconciliation_matches
    if not _table_exists('reconciliation_matches'):
        op.create_table(
            'reconciliation_matches',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('import_id', sa.Integer(),
                      sa.ForeignKey('reconciliation_imports.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('ledger_tx_id', sa.Integer(),
                      sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=True),
            sa.Column('statement_tx_id', sa.String(), nullable=True),
            sa.Column('match_type', sa.String(), nullable=False, default='auto'),
            sa.Column('status', sa.String(), nullable=False, default='matched'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- budget_lines
    if not _table_exists('budget_lines'):
        op.create_table(
            'budget_lines',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('coa_accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('period', sa.String(), nullable=False),
            sa.Column('budget_amount', sa.Numeric(12, 2), nullable=False, default=0),
            sa.Column('actual_amount', sa.Numeric(12, 2), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- tax_line_mappings
    if not _table_exists('tax_line_mappings'):
        op.create_table(
            'tax_line_mappings',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('coa_account_id', sa.Integer(),
                      sa.ForeignKey('coa_accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('form', sa.String(), nullable=False),
            sa.Column('line', sa.String(), nullable=False),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # -- trained_models
    if not _table_exists('trained_models'):
        op.create_table(
            'trained_models',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, default=1),
            sa.Column('model_path', sa.String(), nullable=False),
            sa.Column('model_sha256', sa.String(64), nullable=False),
            sa.Column('accuracy', sa.Numeric(5, 4), nullable=True),
            sa.Column('f1_macro', sa.Numeric(5, 4), nullable=True),
            sa.Column('support', sa.Integer(), nullable=True),
            sa.Column('classes', sa.String(), nullable=True),
            sa.Column('trained_at', sa.DateTime(), nullable=False),
            sa.Column('is_active', sa.Boolean(), default=True),
        )
        op.create_index('ix_trained_models_user_id', 'trained_models', ['user_id'])
        op.create_index('ix_trained_models_tenant_id', 'trained_models', ['tenant_id'])
        op.create_index('ix_trained_models_is_active', 'trained_models', ['is_active'])

    # -- sessions
    if not _table_exists('sessions'):
        op.create_table(
            'sessions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
            sa.Column('token_jti', sa.String(), nullable=True, index=True),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('last_seen_at', sa.DateTime(), nullable=True),
            sa.Column('ip_address', sa.String(), nullable=True),
            sa.Column('user_agent', sa.String(), nullable=True),
        )
        op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])

    # -- refresh_tokens
    if not _table_exists('refresh_tokens'):
        op.create_table(
            'refresh_tokens',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('family_id', sa.String(64), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('replaced_by_token_hash', sa.String(64), nullable=True),
            sa.Column('client_hash', sa.String(64), nullable=True),
        )
        op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    # -- revoked_tokens
    if not _table_exists('revoked_tokens'):
        op.create_table(
            'revoked_tokens',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('jti', sa.String(), unique=True, nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
            sa.Column('token_type', sa.String(), default='access'),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_revoked_tokens_user_id', 'revoked_tokens', ['user_id'])

    # -- audit_entries (ensure it has all v3.11.6 columns)
    if not _table_exists('audit_entries'):
        op.create_table(
            'audit_entries',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('occurred_at', sa.DateTime(), nullable=False),
            sa.Column('actor_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('action', sa.String(), nullable=False),
            sa.Column('resource_type', sa.String(), nullable=False),
            sa.Column('resource_id', sa.Integer(), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('details', sa.String(), default='{}'),
            sa.Column('previous_hash', sa.String(64), default='0' * 64),
            sa.Column('entry_hash', sa.String(64), nullable=False),
            sa.Column('chain_hash', sa.String(64), nullable=True),
            sa.Column('signature', sa.String(), nullable=True),
        )
        op.create_index('ix_audit_entries_actor_id', 'audit_entries', ['actor_id'])
        op.create_index('ix_audit_entries_resource', 'audit_entries',
                        ['resource_type', 'resource_id'])


def downgrade() -> None:
    """Reverse the v3.11.6 COA migration.

    Drops new columns added to existing tables, then drops all tables created
    by this migration.  Tables that existed before v3.11.6 are preserved.
    """
    conn = op.get_bind()

    # Drop coa_account_id columns from existing tables
    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        if 'coa_account_id' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('coa_account_id')

    if _table_exists('general_ledger_entries'):
        gl_cols = _table_columns('general_ledger_entries')
        if 'credit_coa_account_id' in gl_cols:
            with op.batch_alter_table('general_ledger_entries') as batch_op:
                batch_op.drop_column('credit_coa_account_id')
        if 'debit_coa_account_id' in gl_cols:
            with op.batch_alter_table('general_ledger_entries') as batch_op:
                batch_op.drop_column('debit_coa_account_id')

    if _table_exists('categorization_rules'):
        cr_cols = _table_columns('categorization_rules')
        if 'coa_account_id' in cr_cols:
            with op.batch_alter_table('categorization_rules') as batch_op:
                batch_op.drop_column('coa_account_id')

    # Drop tables created by this migration (idempotent)
    for table_name in [
        'tax_line_mappings', 'budget_lines', 'reconciliation_matches',
        'reconciliation_imports', 'fx_rates', 'inventory_transactions',
        'inventory_items', 'investment_lots', 'loan_schedules',
        'payments', 'invoice_line_items', 'invoices',
        'flags', 'general_ledger_entries',
        'periods', 'journals', 'depreciation_assets',
        'trained_models', 'sessions', 'refresh_tokens', 'revoked_tokens',
        'profile_memberships',
    ]:
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {table_name}"))

    # Drop coa_accounts table and its indexes (idempotent)
    for idx_name in [
        'ix_coa_accounts_parent_id',
        'ix_coa_accounts_tenant_number',
        'ix_coa_accounts_tenant_id',
    ]:
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {idx_name}"))
    conn.execute(sa.text("DROP TABLE IF EXISTS coa_accounts"))

