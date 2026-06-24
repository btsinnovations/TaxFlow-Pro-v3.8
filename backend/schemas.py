from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import datetime, date

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str
    keyfile_path: Optional[str] = None

class LocalLogin(BaseModel):
    username: str
    password: str
    keyfile_path: Optional[str] = None

class LocalBoot(BaseModel):
    password: str
    keyfile_path: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    encryption_salt: Optional[str] = None
    keyfile_path: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenPair(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class AuditEntryOut(BaseModel):
    id: int
    occurred_at: datetime
    actor_id: int
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    details: dict = {}
    entry_hash: str
    chain_hash: Optional[str] = None
    signature: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class DepreciationAssetBase(BaseModel):
    name: str
    asset_class: str
    cost_basis: float
    placed_in_service_date: date
    recovery_period_years: int = 5
    method: str = "MACRS-GDS"
    convention: str = "HY"
    section_179: float = 0.0
    bonus_depreciation: float = 0.0
    salvage_value: float = 0.0

class DepreciationAssetCreate(DepreciationAssetBase): pass

class DepreciationAssetUpdate(BaseModel):
    name: Optional[str] = None
    asset_class: Optional[str] = None
    cost_basis: Optional[float] = None
    placed_in_service_date: Optional[date] = None
    recovery_period_years: Optional[int] = None
    method: Optional[str] = None
    convention: Optional[str] = None
    section_179: Optional[float] = None
    bonus_depreciation: Optional[float] = None
    salvage_value: Optional[float] = None

class DepreciationAsset(DepreciationAssetBase):
    id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DepreciationScheduleEntryOut(BaseModel):
    year: int
    beginning_basis: float
    section_179: float
    bonus: float
    regular_depreciation: float
    ending_basis: float

class DepreciationAssetWithSchedule(DepreciationAsset):
    schedule: List[DepreciationScheduleEntryOut] = []


class ClientBase(BaseModel):
    name: str
    email: Optional[str] = None
    tax_id: Optional[str] = None

class ClientCreate(ClientBase): pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    tax_id: Optional[str] = None

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

class Account(AccountBase):
    id: int
    user_id: int
    client_id: int
    tenant_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AccountCreate(AccountBase):
    client_id: int

class TransactionBase(BaseModel):
    date: date
    description: str
    amount: float
    tx_type: str
    category: Optional[str] = "uncategorized"
    running_balance: Optional[float] = None
    workpaper_ref: Optional[str] = None

class Transaction(TransactionBase):
    id: int
    statement_id: int
    tenant_id: int
    gl_account_id: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TransactionUpdate(BaseModel):
    workpaper_ref: Optional[str] = None

class GeneralLedgerEntryOut(BaseModel):
    id: int
    tenant_id: int
    transaction_id: Optional[int] = None
    date: date
    description: Optional[str] = None
    debit_account_id: Optional[int] = None
    credit_account_id: Optional[int] = None
    amount: float
    memo: Optional[str] = None
    workpaper_ref: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class GeneralLedgerEntryCreate(BaseModel):
    date: date
    description: Optional[str] = None
    debit_account_id: Optional[int] = None
    credit_account_id: Optional[int] = None
    amount: float
    memo: Optional[str] = None

class GeneralLedgerEntryUpdate(BaseModel):
    workpaper_ref: Optional[str] = None

class CategorizationRuleCreate(BaseModel):
    name: str
    pattern: str
    gl_account_id: int
    priority: int = 0
    enabled: bool = True

class CategorizationRuleOut(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    name: str
    pattern: str
    gl_account_id: int
    priority: int
    enabled: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CategorizationRuleUpdate(BaseModel):
    name: Optional[str] = None
    pattern: Optional[str] = None
    gl_account_id: Optional[int] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None

class FlagCreate(BaseModel):
    transaction_id: Optional[int] = None
    journal_entry_id: Optional[int] = None
    note: str
    created_by: str = "system"

class FlagOut(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    transaction_id: Optional[int] = None
    journal_entry_id: Optional[int] = None
    note: str
    created_by: str
    resolved: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FlagResolve(BaseModel):
    resolved: bool = True

class WorkpaperRefUpdate(BaseModel):
    workpaper_ref: Optional[str] = None

class GLAccountBase(BaseModel):
    code: str
    name: str
    account_type: str = "expense"

class GLAccountCreate(GLAccountBase): pass

class GLAccount(GLAccountBase):
    id: int
    tenant_id: int
    user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class StatementBase(BaseModel):
    filename: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
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
