from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user")
    created_at = Column(DateTime, server_default=func.now())
    clients = relationship("Client", back_populates="owner")
    accounts = relationship("Account", back_populates="owner")


class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String)
    tax_id = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="clients")
    accounts = relationship("Account", foreign_keys="Account.client_id", back_populates="client")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (Index("ix_accounts_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    institution = Column(String)
    account_number_masked = Column(String)
    type = Column(String, default="checking")
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="accounts")
    client = relationship("Client", foreign_keys=[client_id], back_populates="accounts")
    statements = relationship("Statement", back_populates="account")


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (Index("ix_statements_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String)
    period_start = Column(String)
    period_end = Column(String)
    opening_balance = Column(Numeric(12, 2))
    closing_balance = Column(Numeric(12, 2))
    variance = Column(Numeric(12, 2))
    is_balanced = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())
    account = relationship("Account", back_populates="statements")
    transactions = relationship("Transaction", back_populates="statement")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_tenant_id", "tenant_id"),
        Index("ix_transactions_date", "date"),
        Index("ix_transactions_category", "category"),
    )
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True)
    date = Column(String)
    description = Column(String)
    amount = Column(Numeric(12, 2))
    tx_type = Column(String)
    category = Column(String, default="uncategorized")
    running_balance = Column(Numeric(12, 2), nullable=True)
    confirmed = Column(Boolean, default=False)
    is_manual = Column(Boolean, default=False)
    is_journal = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)
    source_pdf_path = Column(String, nullable=True)
    tax_line = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    statement = relationship("Statement", back_populates="transactions")
    notes = relationship("TransactionNote", back_populates="transaction", cascade="all, delete-orphan")
    flags = relationship("TransactionFlag", back_populates="transaction", cascade="all, delete-orphan")
    journal_entry = relationship("JournalEntry", back_populates="transactions")


class TransactionNote(Base):
    __tablename__ = "transaction_notes"
    __table_args__ = (Index("ix_transaction_notes_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    transaction = relationship("Transaction", back_populates="notes")


class TransactionFlag(Base):
    __tablename__ = "transaction_flags"
    __table_args__ = (Index("ix_transaction_flags_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    flag_type = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    transaction = relationship("Transaction", back_populates="flags")


class AuditEntry(Base):
    __tablename__ = "audit_entries"
    __table_args__ = (Index("ix_audit_entries_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class SignedReport(Base):
    __tablename__ = "signed_reports"
    __table_args__ = (Index("ix_signed_reports_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_type = Column(String, nullable=False)
    period_start = Column(String, nullable=True)
    period_end = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    signed_at = Column(DateTime, server_default=func.now())
    signature_hash = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (Index("ix_journal_entries_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_number = Column(String, nullable=False)
    entry_date = Column(String, nullable=False)
    memo = Column(Text, nullable=True)
    source = Column(String, nullable=True)
    is_reversed = Column(Boolean, default=False)
    reversed_by_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    lines = relationship("JournalEntryLine", back_populates="journal_entry", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="journal_entry")


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (Index("ix_journal_entry_lines_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    account_code = Column(String, nullable=False)
    account_name = Column(String, nullable=True)
    debit = Column(Numeric(12, 2), default=0)
    credit = Column(Numeric(12, 2), default=0)
    memo = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    journal_entry = relationship("JournalEntry", back_populates="lines")


class Period(Base):
    __tablename__ = "periods"
    __table_args__ = (Index("ix_periods_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    status = Column(String, default="open")
    is_locked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (Index("ix_receipts_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    ocr_text = Column(Text, nullable=True)
    vendor = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    receipt_date = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class BankConnection(Base):
    __tablename__ = "bank_connections"
    __table_args__ = (Index("ix_bank_connections_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    institution_name = Column(String, nullable=False)
    connection_type = Column(String, default="ofx")
    status = Column(String, default="active")
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class RecurringTemplate(Base):
    __tablename__ = "recurring_templates"
    __table_args__ = (Index("ix_recurring_templates_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    tx_type = Column(String, nullable=False)
    category = Column(String, default="uncategorized")
    frequency = Column(String, nullable=False)
    day_of_month = Column(Integer, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    last_generated = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (Index("ix_budgets_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    period_start = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    total_budget = Column(Numeric(12, 2), default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    entries = relationship("BudgetEntry", back_populates="budget", cascade="all, delete-orphan")


class BudgetEntry(Base):
    __tablename__ = "budget_entries"
    __table_args__ = (Index("ix_budget_entries_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    budget = relationship("Budget", back_populates="entries")


class BatchImportJob(Base):
    __tablename__ = "batch_import_jobs"
    __table_args__ = (Index("ix_batch_import_jobs_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="pending")
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class FirmSettings(Base):
    __tablename__ = "firm_settings"
    __table_args__ = (Index("ix_firm_settings_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    firm_name = Column(String, nullable=True)
    firm_address = Column(Text, nullable=True)
    firm_phone = Column(String, nullable=True)
    firm_email = Column(String, nullable=True)
    firm_ein = Column(String, nullable=True)
    logo_path = Column(String, nullable=True)
    fiscal_year_end = Column(String, nullable=True)
    timezone = Column(String, default="America/New_York")
    date_format = Column(String, default="%m/%d/%Y")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (Index("ix_exchange_rates_tenant_id", "tenant_id"),)
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Numeric(18, 8), nullable=False)
    rate_date = Column(String, nullable=False)
    source = Column(String, default="manual")
    created_at = Column(DateTime, server_default=func.now())
