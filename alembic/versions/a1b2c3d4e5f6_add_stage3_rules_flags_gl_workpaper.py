"""Add Stage 3 rules, flags, GL accounts, and workpaper refs

Revision ID: a1b2c3d4e5f6
Revises: 377bb18e5f7c
Create Date: 2026-06-20 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '377bb18e5f7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # GL accounts
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
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False, server_default=sa.text('1')))
        batch_op.add_column(sa.Column('gl_account_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('workpaper_ref', sa.String(), nullable=True))
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
