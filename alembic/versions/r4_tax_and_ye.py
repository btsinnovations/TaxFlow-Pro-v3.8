"""v3.11.6 R4: Tax exports and year-end closing.

Adds vendor, sales tax, mileage, and year-end support tables.
Revision ID: r4taxyend
Revises: r2r3merge01_merge_r2_and_r3
"""
from alembic import op
import sqlalchemy as sa

revision = "r4taxyend01"
down_revision = "r2r3merge01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vendor table
    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("tax_id", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("is_1099_eligible", sa.Boolean(), default=False, nullable=False),
        sa.Column("default_expense_coa_account_id", sa.Integer(), sa.ForeignKey("coa_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_vendors_name", "tenant_id", "name"),
    )

    # Sales tax tables
    op.create_table(
        "sales_tax_rates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=False),
        sa.Column("rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_sales_tax_rates_tenant_id", "tenant_id"),
        sa.Index("ix_sales_tax_rates_jurisdiction_effective", "tenant_id", "jurisdiction", "effective_date"),
    )

    op.create_table(
        "sales_tax_payments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_sales_tax_payments_tenant_id", "tenant_id"),
        sa.Index("ix_sales_tax_payments_period", "tenant_id", "period_start", "period_end"),
    )

    # Mileage log table
    op.create_table(
        "mileage_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("starting_odometer", sa.Numeric(12, 2), nullable=False),
        sa.Column("ending_odometer", sa.Numeric(12, 2), nullable=False),
        sa.Column("miles", sa.Numeric(12, 2), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False, default="business"),
        sa.Column("vehicle", sa.String(), nullable=True),
        sa.Column("reimbursement_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("reimbursement_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_mileage_logs_tenant_id", "tenant_id"),
        sa.Index("ix_mileage_logs_trip_date", "tenant_id", "trip_date"),
    )


def downgrade() -> None:
    op.drop_table("mileage_logs")
    op.drop_table("sales_tax_payments")
    op.drop_table("sales_tax_rates")
    op.drop_table("vendors")
