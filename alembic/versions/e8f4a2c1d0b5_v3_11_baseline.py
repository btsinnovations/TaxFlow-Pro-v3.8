"""v3.11 baseline schema

Revision ID: e8f4a2c1d0b5
Revises: ba949088fd32
Create Date: 2026-06-26T01:02:30.457733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e8f4a2c1d0b5'
down_revision: Union[str, Sequence[str], None] = 'ba949088fd32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    """Check whether a table already exists in the target database."""
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    """Idempotent v3.11 baseline: create core tables only if missing."""
    if not _table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('username', sa.String(), unique=True, index=True),
            sa.Column('email', sa.String(), unique=True, index=True),
            sa.Column('hashed_password', sa.String(), nullable=True),
            sa.Column('encryption_salt', sa.String(), nullable=True),
            sa.Column('keyfile_path', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    if not _table_exists('clients'):
        op.create_table(
            'clients',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(), index=True),
            sa.Column('email', sa.String(), nullable=True),
            sa.Column('tax_id', sa.String(), nullable=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    if not _table_exists('accounts'):
        op.create_table(
            'accounts',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('name', sa.String(), nullable=True),
            sa.Column('institution', sa.String(), nullable=True),
            sa.Column('account_number_masked', sa.String(), nullable=True),
            sa.Column('type', sa.String(), default='checking'),
            sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_accounts_tenant_id', 'accounts', ['tenant_id'])

    if not _table_exists('gl_accounts'):
        op.create_table(
            'gl_accounts',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('code', sa.String(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('account_type', sa.String(), nullable=False, default='expense'),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_gl_accounts_tenant_id', 'gl_accounts', ['tenant_id'])

    if not _table_exists('statements'):
        op.create_table(
            'statements',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('filename', sa.String(), nullable=True),
            sa.Column('period_start', sa.Date(), nullable=True),
            sa.Column('period_end', sa.Date(), nullable=True),
            sa.Column('opening_balance', sa.Numeric(12, 2), nullable=True),
            sa.Column('closing_balance', sa.Numeric(12, 2), nullable=True),
            sa.Column('variance', sa.Numeric(12, 2), nullable=True),
            sa.Column('is_balanced', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_statements_tenant_id', 'statements', ['tenant_id'])

    if not _table_exists('transactions'):
        op.create_table(
            'transactions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('statement_id', sa.Integer(), sa.ForeignKey('statements.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('gl_account_id', sa.Integer(), sa.ForeignKey('gl_accounts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('date', sa.Date(), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('amount', sa.Numeric(12, 2), nullable=True),
            sa.Column('tx_type', sa.String(), nullable=True),
            sa.Column('category', sa.String(), default='uncategorized'),
            sa.Column('running_balance', sa.Numeric(12, 2), nullable=True),
            sa.Column('workpaper_ref', sa.String(), nullable=True),
            sa.Column('txn_uid', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_transactions_tenant_id', 'transactions', ['tenant_id'])
        op.create_index('ix_transactions_txn_uid', 'transactions', ['tenant_id', 'user_id', 'txn_uid'], unique=True)

    if not _table_exists('categorization_rules'):
        op.create_table(
            'categorization_rules',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('pattern', sa.String(), nullable=False),
            sa.Column('form', sa.String(), nullable=True),
            sa.Column('line', sa.String(), nullable=True),
            sa.Column('gl_account_id', sa.Integer(), sa.ForeignKey('gl_accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('priority', sa.Integer(), default=0),
            sa.Column('enabled', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_categorization_rules_tenant_id', 'categorization_rules', ['tenant_id'])

    if not _table_exists('recurring_rules'):
        op.create_table(
            'recurring_rules',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), default=0),
            sa.Column('description', sa.String(), default=''),
            sa.Column('frequency', sa.String(), default='monthly'),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('count', sa.Integer(), nullable=True),
            sa.Column('splits_json', sa.String(), default='[]'),
            sa.Column('next_date', sa.Date(), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_recurring_rules_tenant_id', 'recurring_rules', ['tenant_id'])
        op.create_index('ix_recurring_rules_account_id', 'recurring_rules', ['account_id'])

    if not _table_exists('audit_entries'):
        op.create_table(
            'audit_entries',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('occurred_at', sa.DateTime(), default=sa.func.now(), nullable=False),
            sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('action', sa.String(), nullable=False),
            sa.Column('resource_type', sa.String(), nullable=False),
            sa.Column('resource_id', sa.Integer(), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('details', sa.String(), default='{}'),
            sa.Column('previous_hash', sa.String(64), default='0'*64),
            sa.Column('entry_hash', sa.String(64), nullable=False),
            sa.Column('chain_hash', sa.String(64), nullable=True),
            sa.Column('signature', sa.String(), nullable=True),
        )
        op.create_index('ix_audit_entries_actor_id', 'audit_entries', ['actor_id'])
        op.create_index('ix_audit_entries_resource', 'audit_entries', ['resource_type', 'resource_id'])


def downgrade() -> None:
    """Drop baseline tables in reverse dependency order."""
    op.drop_table('recurring_rules')
    op.drop_table('categorization_rules')
    op.drop_index('ix_transactions_txn_uid', table_name='transactions')
    op.drop_index('ix_transactions_tenant_id', table_name='transactions')
    op.drop_table('transactions')
    op.drop_index('ix_statements_tenant_id', table_name='statements')
    op.drop_table('statements')
    op.drop_index('ix_gl_accounts_tenant_id', table_name='gl_accounts')
    op.drop_table('gl_accounts')
    op.drop_index('ix_accounts_tenant_id', table_name='accounts')
    op.drop_table('accounts')
    op.drop_table('clients')
    op.drop_index('ix_audit_entries_resource', table_name='audit_entries')
    op.drop_index('ix_audit_entries_actor_id', table_name='audit_entries')
    op.drop_table('audit_entries')
    op.drop_table('users')
