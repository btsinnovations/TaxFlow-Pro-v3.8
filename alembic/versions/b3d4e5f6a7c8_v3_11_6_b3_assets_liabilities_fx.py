"""v3.11.6 B3: Assets, Liabilities & FX — new tables + transaction FX columns

Revision ID: b3d4e5f6a7c8
Revises: a7c3e9f2b1d4
Create Date: 2026-06-27T23:30:00.000000

This migration adds the B3 bundle tables:
- loan_payments (principal/interest allocation per loan payment)
- credit_lines (revolving credit with simple interest accrual)
- credit_line_transactions (draws and payments on credit lines)
- investment_events (buy/sell/dividend/split events)
- price_snapshots (manual price snapshots for unrealized gains)
- transaction_tags (project tags on transactions)

It also adds FX columns to the transactions table:
- foreign_amount, foreign_currency, fx_rate_snapshot
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = 'b3d4e5f6a7c8'
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
    """Create B3 tables and add FX columns to transactions."""

    # ------------------------------------------------------------------
    # 1. Add FX columns to transactions
    # ------------------------------------------------------------------
    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        if 'foreign_amount' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(
                    sa.Column('foreign_amount', sa.Numeric(12, 2), nullable=True))
        if 'foreign_currency' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(
                    sa.Column('foreign_currency', sa.String(), nullable=True))
        if 'fx_rate_snapshot' not in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.add_column(
                    sa.Column('fx_rate_snapshot', sa.Numeric(18, 8), nullable=True))

    # ------------------------------------------------------------------
    # 2. loan_payments
    # ------------------------------------------------------------------
    if not _table_exists('loan_payments'):
        op.create_table(
            'loan_payments',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('schedule_id', sa.Integer(),
                      sa.ForeignKey('loan_schedules.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('payment_date', sa.Date(), nullable=False),
            sa.Column('payment_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('principal_paid', sa.Numeric(12, 2), nullable=False),
            sa.Column('interest_paid', sa.Numeric(12, 2), nullable=False),
            sa.Column('remaining_principal', sa.Numeric(14, 2), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_loan_payments_tenant_id', 'loan_payments', ['tenant_id'])
        op.create_index('ix_loan_payments_schedule_id', 'loan_payments', ['schedule_id'])

    # ------------------------------------------------------------------
    # 3. credit_lines
    # ------------------------------------------------------------------
    if not _table_exists('credit_lines'):
        op.create_table(
            'credit_lines',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('accounts.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('credit_limit', sa.Numeric(14, 2), nullable=False),
            sa.Column('current_balance', sa.Numeric(14, 2), nullable=False, default=0),
            sa.Column('annual_rate', sa.Numeric(6, 4), nullable=False, default=0),
            sa.Column('last_interest_date', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_credit_lines_tenant_id', 'credit_lines', ['tenant_id'])

    # ------------------------------------------------------------------
    # 4. credit_line_transactions
    # ------------------------------------------------------------------
    if not _table_exists('credit_line_transactions'):
        op.create_table(
            'credit_line_transactions',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('credit_line_id', sa.Integer(),
                      sa.ForeignKey('credit_lines.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('type', sa.String(), nullable=False),
            sa.Column('interest_charge', sa.Numeric(12, 2), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )

    # ------------------------------------------------------------------
    # 5. investment_events
    # ------------------------------------------------------------------
    if not _table_exists('investment_events'):
        op.create_table(
            'investment_events',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('account_id', sa.Integer(),
                      sa.ForeignKey('accounts.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('symbol', sa.String(), nullable=False),
            sa.Column('event_type', sa.String(), nullable=False),
            sa.Column('event_date', sa.Date(), nullable=False),
            sa.Column('shares', sa.Numeric(14, 6), nullable=False, default=0),
            sa.Column('amount', sa.Numeric(14, 4), nullable=False, default=0),
            sa.Column('split_ratio', sa.String(), nullable=True),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_investment_events_tenant_id',
                        'investment_events', ['tenant_id'])

    # ------------------------------------------------------------------
    # 6. price_snapshots
    # ------------------------------------------------------------------
    if not _table_exists('price_snapshots'):
        op.create_table(
            'price_snapshots',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('symbol', sa.String(), nullable=False),
            sa.Column('price', sa.Numeric(14, 4), nullable=False),
            sa.Column('snapshot_date', sa.Date(), nullable=False),
            sa.Column('source', sa.String(), nullable=False, default='manual'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_price_snapshots_tenant_id',
                        'price_snapshots', ['tenant_id'])

    # ------------------------------------------------------------------
    # 7. transaction_tags
    # ------------------------------------------------------------------
    if not _table_exists('transaction_tags'):
        op.create_table(
            'transaction_tags',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('transaction_id', sa.Integer(),
                      sa.ForeignKey('transactions.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('clients.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('user_id', sa.Integer(),
                      sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('tag', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index('ix_transaction_tags_tenant_id',
                        'transaction_tags', ['tenant_id'])
        op.create_index('ix_transaction_tags_transaction_id',
                        'transaction_tags', ['transaction_id'])


def downgrade() -> None:
    """Reverse the B3 migration."""

    # Drop B3 tables
    for tbl in [
        'transaction_tags', 'price_snapshots', 'investment_events',
        'credit_line_transactions', 'credit_lines', 'loan_payments',
    ]:
        if _table_exists(tbl):
            try:
                op.drop_table(tbl)
            except Exception:
                pass

    # Remove FX columns from transactions
    if _table_exists('transactions'):
        tx_cols = _table_columns('transactions')
        if 'fx_rate_snapshot' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('fx_rate_snapshot')
        if 'foreign_currency' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('foreign_currency')
        if 'foreign_amount' in tx_cols:
            with op.batch_alter_table('transactions') as batch_op:
                batch_op.drop_column('foreign_amount')