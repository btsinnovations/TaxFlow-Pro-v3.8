from datetime import date, datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class AuditEntry(Base):
    __tablename__ = "audit_entries"
    id = Column(Integer, primary_key=True, index=True)
    occurred_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    details = Column(String, default="{}")
    previous_hash = Column(String(64), default="0" * 64)
    entry_hash = Column(String(64), nullable=False)
    chain_hash = Column(String(64), nullable=True)
    signature = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_audit_entries_actor_id", "actor_id"),
        Index("ix_audit_entries_resource", "resource_type", "resource_id"),
    )

    actor = relationship("User", back_populates="audit_entries")

    def details_dict(self):
        import json
        try:
            return json.loads(self.details or "{}")
        except json.JSONDecodeError:
            return {}


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    token_type = Column(String, default="access")
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_revoked_tokens_user_id", "user_id"),
    )

    user = relationship("User", back_populates="revoked_tokens")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_id = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_token_hash = Column(String(64), nullable=True)
    client_hash = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
    )

    user = relationship("User", back_populates="refresh_tokens")

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    token_jti = Column(String, index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
    )

    user = relationship("User", back_populates="sessions")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    encryption_salt = Column(String, nullable=True)
    keyfile_path = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    clients = relationship("Client", back_populates="owner")
    accounts = relationship("Account", back_populates="owner")
    assets = relationship("DepreciationAsset", back_populates="owner")
    journals = relationship("Journal", back_populates="owner")
    periods = relationship("Period", back_populates="owner")
    audit_entries = relationship("AuditEntry", back_populates="actor")
    revoked_tokens = relationship("RevokedToken", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
    sessions = relationship("Session", back_populates="user")
    trained_models = relationship("TrainedModel", back_populates="owner")
    memberships = relationship("ProfileMembership", back_populates="user", cascade="all, delete-orphan")


class ProfileMembership(Base):
    __tablename__ = "profile_memberships"
    __table_args__ = (
        Index("ix_profile_memberships_profile_id", "profile_id"),
        Index("ix_profile_memberships_user_id", "user_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False, default="viewer")
    created_at = Column(DateTime, server_default=func.now())
    profile = relationship("Client", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String)
    tax_id = Column(String)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="clients")
    accounts = relationship("Account", foreign_keys="Account.client_id", back_populates="client")
    memberships = relationship("ProfileMembership", back_populates="profile", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_accounts_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    institution = Column(String)
    account_number_masked = Column(String)
    type = Column(String, default="checking")
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="accounts")
    client = relationship("Client", foreign_keys=[client_id], back_populates="accounts")
    statements = relationship("Statement", back_populates="account")


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (
        Index("ix_statements_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String)
    period_start = Column(Date)
    period_end = Column(Date)
    opening_balance = Column(Numeric(12, 2))
    closing_balance = Column(Numeric(12, 2))
    variance = Column(Numeric(12, 2))
    is_balanced = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())
    account = relationship("Account", back_populates="statements")
    transactions = relationship("Transaction", back_populates="statement")


class DepreciationAsset(Base):
    __tablename__ = "depreciation_assets"
    __table_args__ = (
        Index("ix_depreciation_assets_tenant_id", "tenant_id"),
        Index("ix_depreciation_assets_user_id", "user_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    asset_class = Column(String, nullable=False)
    cost_basis = Column(Numeric(14, 2), nullable=False)
    placed_in_service_date = Column(Date, nullable=False)
    recovery_period_years = Column(Integer, nullable=False)
    method = Column(String, nullable=False, default="MACRS-GDS")
    convention = Column(String, nullable=False, default="HY")
    section_179 = Column(Numeric(14, 2), nullable=False, default=0)
    bonus_depreciation = Column(Numeric(14, 2), nullable=False, default=0)
    salvage_value = Column(Numeric(14, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="assets")


class Journal(Base):
    __tablename__ = "journals"
    __table_args__ = (
        Index("ix_journals_tenant_id", "tenant_id"),
        Index("ix_journals_user_id", "user_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    memo = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="journals")


class Period(Base):
    __tablename__ = "periods"
    __table_args__ = (
        Index("ix_periods_tenant_id", "tenant_id"),
        Index("ix_periods_user_id", "user_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, default=False)
    closed_at = Column(DateTime, nullable=True)
    closed_by_profile_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="periods")


class CoaAccount(Base):
    """Chart of Accounts entry — the v3.11.6 replacement for GLAccount.

    Supports hierarchical COA with parent_id self-reference, integer account
    numbers, and the five canonical bookkeeping types.
    """
    __tablename__ = "coa_accounts"
    __table_args__ = (
        Index("ix_coa_accounts_tenant_id", "tenant_id"),
        Index("ix_coa_accounts_tenant_number", "tenant_id", "number", unique=True),
        Index("ix_coa_accounts_parent_id", "parent_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="SET NULL"), nullable=True)
    number = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False, default="expense")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))

    parent = relationship("CoaAccount", remote_side=[id], backref="children")

    # Cross-references — these mirror the GLAccount relationships so the COA
    # service can guard against deletion when transactions or ledger entries
    # reference the account.
    transactions = relationship("Transaction", back_populates="coa_account", foreign_keys="Transaction.coa_account_id")
    ledger_entries_debit = relationship("GeneralLedgerEntry", back_populates="debit_coa_account", foreign_keys="GeneralLedgerEntry.debit_coa_account_id")
    ledger_entries_credit = relationship("GeneralLedgerEntry", back_populates="credit_coa_account", foreign_keys="GeneralLedgerEntry.credit_coa_account_id")
    categorization_rules = relationship("CategorizationRule", back_populates="coa_account", foreign_keys="CategorizationRule.coa_account_id")


class GLAccount(Base):
    __tablename__ = "gl_accounts"
    __table_args__ = (
        Index("ix_gl_accounts_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    account_type = Column(String, nullable=False, default="expense")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    owner = relationship("User")
    categorization_rules = relationship("CategorizationRule", back_populates="gl_account")
    transactions = relationship("Transaction", back_populates="gl_account")


class CategorizationRule(Base):
    __tablename__ = "categorization_rules"
    __table_args__ = (
        Index("ix_categorization_rules_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    pattern = Column(String, nullable=False)
    form = Column(String, nullable=True)
    line = Column(String, nullable=True)
    gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False)
    coa_account_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="SET NULL"), nullable=True)
    priority = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    gl_account = relationship("GLAccount", back_populates="categorization_rules")
    coa_account = relationship("CoaAccount", back_populates="categorization_rules")


class GeneralLedgerEntry(Base):
    __tablename__ = "general_ledger_entries"
    __table_args__ = (
        Index("ix_general_ledger_entries_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=True)
    date = Column(Date, nullable=False)
    description = Column(String)
    debit_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True)
    credit_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True)
    debit_coa_account_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="SET NULL"), nullable=True)
    credit_coa_account_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    memo = Column(String)
    workpaper_ref = Column(String, nullable=True)
    entry_type = Column(String, nullable=True, default="regular")
    source_id = Column(String, nullable=True)
    import_source = Column(String, nullable=True)
    txn_uid = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    transaction = relationship("Transaction", back_populates="ledger_entries")
    flags = relationship("Flag", back_populates="journal_entry")
    debit_coa_account = relationship("CoaAccount", back_populates="ledger_entries_debit", foreign_keys=[debit_coa_account_id])
    credit_coa_account = relationship("CoaAccount", back_populates="ledger_entries_credit", foreign_keys=[credit_coa_account_id])


class Flag(Base):
    __tablename__ = "flags"
    __table_args__ = (
        Index("ix_flags_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=True)
    journal_entry_id = Column(Integer, ForeignKey("general_ledger_entries.id", ondelete="CASCADE"), nullable=True)
    note = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    transaction = relationship("Transaction", back_populates="flags")
    journal_entry = relationship("GeneralLedgerEntry", back_populates="flags")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_tenant_id", "tenant_id"),
        Index("ix_transactions_txn_uid", "tenant_id", "user_id", "txn_uid", unique=True),
    )
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gl_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True)
    coa_account_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="SET NULL"), nullable=True)
    date = Column(Date)
    description = Column(String)
    amount = Column(Numeric(12, 2))
    tx_type = Column(String)
    category = Column(String, default="uncategorized")
    running_balance = Column(Numeric(12, 2), nullable=True)
    workpaper_ref = Column(String, nullable=True)
    txn_uid = Column(String, nullable=True)
    fitid = Column(String, nullable=True, index=True)
    import_source = Column(String, nullable=True)
    # B3.04 — Multi-currency fields
    foreign_amount = Column(Numeric(12, 2), nullable=True)
    foreign_currency = Column(String, nullable=True)
    fx_rate_snapshot = Column(Numeric(18, 8), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    statement = relationship("Statement", back_populates="transactions")
    gl_account = relationship("GLAccount", back_populates="transactions")
    coa_account = relationship("CoaAccount", back_populates="transactions")
    ledger_entries = relationship("GeneralLedgerEntry", back_populates="transaction")
    flags = relationship("Flag", back_populates="transaction")
    project_tags = relationship("TransactionTag", back_populates="transaction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Transaction(id={self.id}, date={self.date}, amount={self.amount})>"

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat() if self.date else None,
            "description": self.description,
            "amount": float(self.amount) if self.amount is not None else None,
            "tx_type": self.tx_type,
            "category": self.category,
            "running_balance": float(self.running_balance) if self.running_balance is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "statement_id": self.statement_id,
            "tenant_id": self.tenant_id,
            "gl_account_id": self.gl_account_id,
            "workpaper_ref": self.workpaper_ref,
            "txn_uid": self.txn_uid,
            "import_source": self.import_source,
            "foreign_amount": float(self.foreign_amount) if self.foreign_amount is not None else None,
            "foreign_currency": self.foreign_currency,
            "fx_rate_snapshot": float(self.fx_rate_snapshot) if self.fx_rate_snapshot is not None else None,
        }


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    contact_name = Column(String, nullable=False)
    invoice_number = Column(String, nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    total = Column(Numeric(12, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String, nullable=False, default="open")
    is_bill = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    description = Column(String, nullable=False)
    qty = Column(Numeric(12, 4), nullable=False, default=1)
    rate = Column(Numeric(12, 4), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    invoice = relationship("Invoice", back_populates="line_items")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    method = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, server_default=func.now())
    invoice = relationship("Invoice", back_populates="payments")


class LoanSchedule(Base):
    __tablename__ = "loan_schedules"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_principal = Column(Numeric(14, 2), nullable=False)
    rate = Column(Numeric(6, 4), nullable=False)
    term_months = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    payment_amount = Column(Numeric(12, 2), nullable=False)
    schedule_json = Column(String, default="[]")
    created_at = Column(DateTime, server_default=func.now())


class InvestmentLot(Base):
    __tablename__ = "investment_lots"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    shares = Column(Numeric(14, 6), nullable=False)
    cost_basis = Column(Numeric(14, 4), nullable=False)
    acquisition_date = Column(Date, nullable=False)
    sale_date = Column(Date, nullable=True)
    sale_proceeds = Column(Numeric(14, 4), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sku = Column(String, nullable=False)
    name = Column(String, nullable=False)
    cogs_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True)
    income_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True)
    asset_account_id = Column(Integer, ForeignKey("gl_accounts.id", ondelete="SET NULL"), nullable=True)
    valuation_method = Column(String, nullable=False, default="average")
    qty_on_hand = Column(Numeric(12, 4), nullable=False, default=0)
    unit_cost = Column(Numeric(12, 4), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Numeric(12, 4), nullable=False)
    unit_cost = Column(Numeric(12, 4), nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)
    type = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class FXRate(Base):
    __tablename__ = "fx_rates"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    effective_date = Column(Date, nullable=False)
    source = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, server_default=func.now())


class ReconciliationImport(Base):
    __tablename__ = "reconciliation_imports"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    import_date = Column(Date, nullable=False)
    statement_date = Column(Date, nullable=True)
    statement_balance = Column(Numeric(12, 2), nullable=False)
    filename = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    completed_by_profile_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"
    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("reconciliation_imports.id", ondelete="CASCADE"), nullable=False)
    ledger_tx_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=True)
    statement_tx_id = Column(String, nullable=True)
    match_type = Column(String, nullable=False, default="auto")
    status = Column(String, nullable=False, default="matched")
    created_at = Column(DateTime, server_default=func.now())


class BudgetLine(Base):
    __tablename__ = "budget_lines"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="CASCADE"), nullable=False)
    period = Column(String, nullable=False)
    budget_amount = Column(Numeric(12, 2), nullable=False, default=0)
    actual_amount = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())


class TaxLineMapping(Base):
    __tablename__ = "tax_line_mappings"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    coa_account_id = Column(Integer, ForeignKey("coa_accounts.id", ondelete="CASCADE"), nullable=False)
    form = Column(String, nullable=False)
    line = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class RecurringRule(Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        Index("ix_recurring_rules_tenant_id", "tenant_id"),
        Index("ix_recurring_rules_account_id", "account_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    description = Column(String, nullable=False, default="")
    frequency = Column(String, nullable=False, default="monthly")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    count = Column(Integer, nullable=True)
    splits_json = Column(String, default="[]")
    next_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class TrainedModel(Base):
    __tablename__ = "trained_models"
    __table_args__ = (
        Index("ix_trained_models_user_id", "user_id"),
        Index("ix_trained_models_tenant_id", "tenant_id"),
        Index("ix_trained_models_is_active", "is_active"),
    )
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    model_path = Column(String, nullable=False)
    model_sha256 = Column(String(64), nullable=False)
    accuracy = Column(Numeric(5, 4), nullable=True)
    f1_macro = Column(Numeric(5, 4), nullable=True)
    support = Column(Integer, nullable=True)
    classes = Column(String, nullable=True)
    trained_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True)

    owner = relationship("User", back_populates="trained_models")


class LoanPayment(Base):
    """B3.01 — Track individual loan payments with principal/interest allocation."""
    __tablename__ = "loan_payments"
    __table_args__ = (
        Index("ix_loan_payments_tenant_id", "tenant_id"),
        Index("ix_loan_payments_schedule_id", "schedule_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("loan_schedules.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    payment_date = Column(Date, nullable=False)
    payment_amount = Column(Numeric(12, 2), nullable=False)
    principal_paid = Column(Numeric(12, 2), nullable=False)
    interest_paid = Column(Numeric(12, 2), nullable=False)
    remaining_principal = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CreditLine(Base):
    """B3.01 — Revolving credit line with simple interest accrual."""
    __tablename__ = "credit_lines"
    __table_args__ = (
        Index("ix_credit_lines_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    credit_limit = Column(Numeric(14, 2), nullable=False)
    current_balance = Column(Numeric(14, 2), nullable=False, default=0)
    annual_rate = Column(Numeric(6, 4), nullable=False, default=0)
    last_interest_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class CreditLineTransaction(Base):
    """B3.01 — Individual draw/payment on a credit line."""
    __tablename__ = "credit_line_transactions"
    id = Column(Integer, primary_key=True, index=True)
    credit_line_id = Column(Integer, ForeignKey("credit_lines.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    type = Column(String, nullable=False)
    interest_charge = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())


class InvestmentEvent(Base):
    """B3.02 — Dividend, split, and other investment events."""
    __tablename__ = "investment_events"
    __table_args__ = (
        Index("ix_investment_events_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    event_date = Column(Date, nullable=False)
    shares = Column(Numeric(14, 6), nullable=False, default=0)
    amount = Column(Numeric(14, 4), nullable=False, default=0)
    split_ratio = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class PriceSnapshot(Base):
    """B3.02 — Manual price snapshot for unrealized gain calculation."""
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index("ix_price_snapshots_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Numeric(14, 4), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    source = Column(String, nullable=False, default="manual")
    created_at = Column(DateTime, server_default=func.now())


class TransactionTag(Base):
    """B3.03 — Project tags attached to transactions."""
    __tablename__ = "transaction_tags"
    __table_args__ = (
        Index("ix_transaction_tags_tenant_id", "tenant_id"),
        Index("ix_transaction_tags_transaction_id", "transaction_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    transaction = relationship("Transaction", back_populates="project_tags")

