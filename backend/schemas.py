from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    role: str = "user"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenWithUser(Token):
    user: User

class ClientBase(BaseModel):
    name: str
    email: Optional[str] = None
    tax_id: Optional[str] = None

class ClientCreate(ClientBase): pass

class ClientUpdate(ClientBase): pass

class Client(ClientBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AccountBase(BaseModel):
    name: str
    institution: Optional[str] = None
    account_number_masked: Optional[str] = None
    type: str = "checking"

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    institution: Optional[str] = None
    account_number_masked: Optional[str] = None
    type: Optional[str] = None
    client_id: Optional[int] = None

class AccountCreate(AccountBase):
    client_id: int

class Account(AccountBase):
    id: int
    user_id: int
    client_id: int
    tenant_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TransactionBase(BaseModel):
    date: str
    description: str
    amount: float
    tx_type: str
    category: Optional[str] = "uncategorized"
    running_balance: Optional[float] = None

class Transaction(TransactionBase):
    id: int
    statement_id: int
    tenant_id: int
    client_id: Optional[int] = None
    journal_entry_id: Optional[int] = None
    receipt_id: Optional[int] = None
    confirmed: bool = False
    is_manual: bool = False
    is_journal: bool = False
    archived: bool = False
    source_pdf_path: Optional[str] = None
    tax_line: Optional[str] = None
    split_id: Optional[str] = None
    parent_id: Optional[str] = None
    memo: Optional[str] = None
    graph_edges: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class StatementBase(BaseModel):
    filename: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    variance: Optional[float] = None
    is_balanced: Optional[bool] = None

class Statement(StatementBase):
    id: int
    account_id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    transactions: List[Transaction] = []
    model_config = ConfigDict(from_attributes=True)

class AccountWithStatements(Account):
    statements: List[Statement] = []


# ==================== TransactionNote ====================

class TransactionNoteBase(BaseModel):
    note: str

class TransactionNoteCreate(TransactionNoteBase):
    transaction_id: int

class TransactionNote(TransactionNoteBase):
    id: int
    transaction_id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== TransactionFlag ====================

class TransactionFlagBase(BaseModel):
    flag_type: str
    reason: Optional[str] = None
    is_resolved: bool = False

class TransactionFlagCreate(TransactionFlagBase):
    transaction_id: int

class TransactionFlag(TransactionFlagBase):
    id: int
    transaction_id: int
    tenant_id: int
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== AuditEntry ====================

class AuditEntryBase(BaseModel):
    action: str
    entity_type: str
    entity_id: int
    details: Optional[str] = None

class AuditEntryCreate(AuditEntryBase):
    pass

class AuditEntry(AuditEntryBase):
    id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== SignedReport ====================

class SignedReportBase(BaseModel):
    report_type: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    file_path: Optional[str] = None
    signature_hash: Optional[str] = None

class SignedReportCreate(SignedReportBase):
    pass

class SignedReport(SignedReportBase):
    id: int
    tenant_id: int
    user_id: int
    signed_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== JournalEntry ====================

class JournalEntryLineBase(BaseModel):
    account_code: str
    account_name: Optional[str] = None
    debit: float = 0
    credit: float = 0
    memo: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class JournalEntryLineCreate(JournalEntryLineBase):
    pass

class JournalEntryLine(JournalEntryLineBase):
    id: int
    journal_entry_id: int
    tenant_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class JournalEntryBase(BaseModel):
    entry_number: str
    entry_date: str
    memo: Optional[str] = None
    source: Optional[str] = None

class JournalEntryCreate(JournalEntryBase):
    lines: List[JournalEntryLineCreate] = []

class JournalEntry(JournalEntryBase):
    id: int
    tenant_id: int
    user_id: int
    is_reversed: bool = False
    reversed_by_id: Optional[int] = None
    lines: List[JournalEntryLine] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ==================== Period ====================

class PeriodBase(BaseModel):
    name: str
    start_date: str
    end_date: str
    status: str = "open"
    is_locked: bool = False

class PeriodCreate(PeriodBase):
    pass

class Period(PeriodBase):
    id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== Receipt ====================

class ReceiptBase(BaseModel):
    filename: str
    file_path: str
    ocr_text: Optional[str] = None
    vendor: Optional[str] = None
    amount: Optional[float] = None
    receipt_date: Optional[str] = None

class ReceiptCreate(ReceiptBase):
    transaction_id: Optional[int] = None

class Receipt(ReceiptBase):
    id: int
    tenant_id: int
    user_id: int
    transaction_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== BankConnection ====================

class BankConnectionBase(BaseModel):
    institution_name: str
    connection_type: str = "ofx"
    status: str = "active"

class BankConnectionCreate(BankConnectionBase):
    account_id: int

class BankConnection(BankConnectionBase):
    id: int
    tenant_id: int
    user_id: int
    account_id: int
    last_sync: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== RecurringTemplate ====================

class RecurringTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    amount: float
    tx_type: str
    category: str = "uncategorized"
    frequency: str
    day_of_month: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_active: bool = True

class RecurringTemplateCreate(RecurringTemplateBase):
    pass

class RecurringTemplate(RecurringTemplateBase):
    id: int
    tenant_id: int
    user_id: int
    last_generated: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== Budget ====================

class BudgetEntryBase(BaseModel):
    category: str
    amount: float

class BudgetEntryCreate(BudgetEntryBase):
    pass

class BudgetEntry(BudgetEntryBase):
    id: int
    budget_id: int
    tenant_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BudgetBase(BaseModel):
    name: str
    period_start: str
    period_end: str
    total_budget: float = 0
    is_active: bool = True

class BudgetCreate(BudgetBase):
    entries: List[BudgetEntryCreate] = []

class Budget(BudgetBase):
    id: int
    tenant_id: int
    user_id: int
    entries: List[BudgetEntry] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== BatchImportJob ====================

class BatchImportJobBase(BaseModel):
    filename: str

class BatchImportJobCreate(BatchImportJobBase):
    pass

class BatchImportJob(BatchImportJobBase):
    id: int
    tenant_id: int
    user_id: int
    status: str = "pending"
    total_rows: int = 0
    processed_rows: int = 0
    error_rows: int = 0
    error_log: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ==================== FirmSettings ====================

class FirmSettingsBase(BaseModel):
    firm_name: Optional[str] = None
    firm_address: Optional[str] = None
    firm_phone: Optional[str] = None
    firm_email: Optional[str] = None
    firm_ein: Optional[str] = None
    logo_path: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    recurring_high_confidence: float = 0.95
    recurring_medium_confidence: float = 0.75
    recurring_auto_confirm: float = 0.90
    receipt_match_amount_weight: float = 0.40
    receipt_match_date_weight: float = 0.35
    receipt_match_description_weight: float = 0.25
    timezone: str = "America/New_York"
    date_format: str = "%m/%d/%Y"
    ml_enabled: bool = False

class FirmSettingsCreate(FirmSettingsBase):
    pass

class FirmSettings(FirmSettingsBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ==================== ExchangeRate ====================

class ExchangeRateBase(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    rate_date: str
    source: str = "manual"

class ExchangeRateCreate(ExchangeRateBase):
    pass

class ExchangeRate(ExchangeRateBase):
    id: int
    tenant_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== TaxExport ====================

class TaxExportBase(BaseModel):
    export_type: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    format: str = "json"

class TaxExportCreate(TaxExportBase):
    pass

class TaxExport(TaxExportBase):
    id: int
    tenant_id: int
    user_id: int
    file_path: Optional[str] = None
    status: str = "pending"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== Forecast ====================

class ForecastBase(BaseModel):
    name: str
    period_start: str
    period_end: str
    scenario: str = "baseline"

class ForecastCreate(ForecastBase):
    pass

class Forecast(ForecastBase):
    id: int
    tenant_id: int
    user_id: int
    projected_income: float = 0
    projected_expense: float = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== Engagement Templates ====================

class EngagementBase(BaseModel):
    name: str
    description: Optional[str] = None
    checklist: Optional[str] = None
    due_date: Optional[str] = None
    status: str = "draft"

class EngagementCreate(EngagementBase):
    pass

class Engagement(EngagementBase):
    id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
