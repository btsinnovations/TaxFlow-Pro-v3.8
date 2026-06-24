"""Add audit entries and depreciation assets

Revision ID: e8b7c1d5f3a2
Revises: b9f4e2c8d310
Create Date: 2026-06-19 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b7c1d5f3a2'
down_revision: Union[str, Sequence[str], None] = 'b9f4e2c8d310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.String(), nullable=True),
        sa.Column('previous_hash', sa.String(length=64), nullable=True),
        sa.Column('entry_hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_entries_actor_id', 'audit_entries', ['actor_id'], unique=False)
    op.create_index('ix_audit_entries_resource', 'audit_entries', ['resource_type', 'resource_id'], unique=False)

    op.create_table(
        'depreciation_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('asset_class', sa.String(), nullable=False),
        sa.Column('cost_basis', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('placed_in_service_date', sa.Date(), nullable=False),
        sa.Column('recovery_period_years', sa.Integer(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('convention', sa.String(), nullable=False),
        sa.Column('section_179', sa.Numeric(precision=14, scale=2), server_default=sa.text('0.00'), nullable=False),
        sa.Column('bonus_depreciation', sa.Numeric(precision=14, scale=2), server_default=sa.text('0.00'), nullable=False),
        sa.Column('salvage_value', sa.Numeric(precision=14, scale=2), server_default=sa.text('0.00'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_depreciation_assets_id', 'depreciation_assets', ['id'], unique=False)
    op.create_index('ix_depreciation_assets_tenant_id', 'depreciation_assets', ['tenant_id'], unique=False)
    op.create_index('ix_depreciation_assets_user_id', 'depreciation_assets', ['user_id'], unique=False)

    op.create_table(
        'journals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('memo', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_journals_tenant_id', 'journals', ['tenant_id'], unique=False)
    op.create_index('ix_journals_user_id', 'journals', ['user_id'], unique=False)

    op.create_table(
        'periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('start_date', sa.String(), nullable=False),
        sa.Column('end_date', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_periods_tenant_id', 'periods', ['tenant_id'], unique=False)
    op.create_index('ix_periods_user_id', 'periods', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_periods_user_id', table_name='periods')
    op.drop_index('ix_periods_tenant_id', table_name='periods')
    op.drop_table('periods')

    op.drop_index('ix_journals_user_id', table_name='journals')
    op.drop_index('ix_journals_tenant_id', table_name='journals')
    op.drop_table('journals')
    op.drop_index('ix_depreciation_assets_user_id', table_name='depreciation_assets')
    op.drop_index('ix_depreciation_assets_tenant_id', table_name='depreciation_assets')
    op.drop_index('ix_depreciation_assets_id', table_name='depreciation_assets')
    op.drop_table('depreciation_assets')

    op.drop_index('ix_audit_entries_resource', table_name='audit_entries')
    op.drop_index('ix_audit_entries_actor_id', table_name='audit_entries')
    op.drop_table('audit_entries')
