"""v3.11.6 B2 Transaction Engine: splits, tags, status columns + checks table

Revision ID: b2a1c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-27T22:00:00.000000

This migration:
1. Adds ``splits`` (JSON/Text), ``tags`` (String), and ``status`` (String)
   columns to the ``transactions`` table.
2. Creates the ``checks`` table for tracking physical checks issued.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = 'b2a1c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9f2b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _table_columns(table_name: str) -> set:
    conn = op.get_bind()
    try:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {row[1] for row in rows}
    except Exception:
        return set()


def upgrade() -> None:
    """Add splits/tags/status to transactions; create checks table."""
    # ------------------------------------------------------------------
    # 1. Add new columns to transactions
    # ------------------------------------------------------------------
    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        if 'splits' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(sa.Column('splits', sa.Text(), default='[]'))
        if 'tags' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(sa.Column('tags', sa.String(), default=''))
        if 'status' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(sa.Column('status', sa.String(), default='pending'))

    # ------------------------------------------------------------------
    # 2. Create checks table
    # ------------------------------------------------------------------
    if not _table_exists('checks'):
        op.create_table(
            'checks',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('check_number', sa.String(), nullable=False),
            sa.Column('payee', sa.String(), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('memo', sa.String(), nullable=True),
            sa.Column('status', sa.String(), default='pending'),
            sa.Column('transaction_id', sa.Integer(),
                      sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_checks_tenant_id', 'checks', ['tenant_id'])
        op.create_index('ix_checks_account_number', 'checks',
                        ['account_id', 'check_number'], unique=True)


def downgrade() -> None:
    """Reverse the B2 migration."""
    if _table_exists('checks'):
        try:
            op.drop_index('ix_checks_account_number', table_name='checks')
        except Exception:
            pass
        try:
            op.drop_index('ix_checks_tenant_id', table_name='checks')
        except Exception:
            pass
        try:
            op.drop_table('checks')
        except Exception:
            pass

    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        if 'status' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('status')
        if 'tags' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('tags')
        if 'splits' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('splits')