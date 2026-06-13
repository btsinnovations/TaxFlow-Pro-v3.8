from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal

# ==================== HEALTH ====================

class HealthResponse(BaseModel):
    status: str
    version: str
    pipeline: str


# ==================== CLIENTS ====================

class ClientCreate(BaseModel):
    name: str
    entity_type: Optional[str] = "Individual"
    tax_id: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    entity_type: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None


class ClientOut(BaseModel):
    id: str
    name: str
    entity_type: str
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    documents_processed: int = 0
    accounts_linked: int = 0
    status: str = "Active"


# ==================== UPLOAD / PROCESS ====================

class UploadResponse(BaseModel):
    success: bool
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    message: str


class ProcessingRequest(BaseModel):
    file_id: str
    client_id: str = "default"
    output_format: str = "qif"
    use_fast: bool = False
    use_ml: bool = True
    profile: Optional[str] = "personal"
    source_folder: Optional[str] = None
    output_folder: Optional[str] = None


class TransactionOut(BaseModel):
    date: str
    description: str
    raw_description: str = ""
    amount: str
    category: Optional[str] = None
    payee: str = "unknown"
    institution: str = "unknown"
    txn_uid: str
    tax_category: str = "uncategorized"
    tax_deductible: bool = False
    memo: str = ""

    @field_validator('amount', mode='before')
    @classmethod
    def convert_amount(cls, v):
        if isinstance(v, (Decimal, int, float)):
            return str(v)
        return v


class ReconciliationOut(BaseModel):
    status: str
    message: str
    opening_balance: Optional[str] = None
    closing_balance: Optional[str] = None
    transaction_count: int
    total_credits: str
    total_debits: str
    net_change: str
    calculated_ending: Optional[str] = None
    variance: str


class ProcessingResult(BaseModel):
    success: bool
    file_id: str
    client_id: str
    institution: str
    transaction_count: int
    transactions: List[TransactionOut]
    reconciliation: ReconciliationOut
    output_file: Optional[str] = None
    processing_time_ms: int
    warnings: List[str] = []


# ==================== AUDIT ====================

class AuditEventOut(BaseModel):
    id: str
    timestamp: str
    severity: str
    event_type: str
    client_id: Optional[str] = None
    description: str
    user: str
    session_id: str
    details: Optional[Dict[str, Any]] = None


# ==================== TAX ====================

class TaxRuleOut(BaseModel):
    id: str
    name: str
    category: str
    description: str
    applies_to: List[str]
    effective_date: str
    threshold: Optional[str] = None
    maximum: Optional[str] = None
    override_allowed: bool = False
    auto_apply: bool = False


class TaxRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    threshold: Optional[str] = None
    maximum: Optional[str] = None
    override_allowed: Optional[bool] = None
    auto_apply: Optional[bool] = None


# ==================== ML ====================

class MLModelStatus(BaseModel):
    enabled: bool
    model_version: Optional[str] = None
    accuracy: Optional[float] = None
    last_trained: Optional[str] = None
    training_samples: Optional[int] = None


class MLTrainingRequest(BaseModel):
    epochs: Optional[int] = 10
    learning_rate: Optional[float] = 0.001
    batch_size: Optional[int] = 32
    validation_split: Optional[float] = 0.2
    early_stopping: Optional[bool] = True


# ==================== EXPORT ====================

class ExportFormatOut(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    color: str
    status: str


# ==================== TESTS ====================

class TestResultOut(BaseModel):
    name: str
    category: str
    status: str
    duration: str
    details: str


class TestRunOut(BaseModel):
    success: bool
    total: int
    passed: int
    failed: int
    skipped: int
    results: List[TestResultOut]
    execution_time_ms: int


# ==================== DASHBOARD ====================



# ==================== ACCOUNTS ====================

class AccountCreate(BaseModel):
    client_id: str
    nickname: str
    institution: str
    account_type: str = "Checking"
    account_number_last4: Optional[str] = None
    notes: Optional[str] = None


class AccountOut(BaseModel):
    id: str
    client_id: str
    nickname: str
    institution: str
    account_type: str
    account_number_last4: Optional[str] = None
    last_sync: Optional[str] = None
    status: str = "Connected"
    fragility_score: int = 0
    notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class AccountUpdate(BaseModel):
    nickname: Optional[str] = None
    institution: Optional[str] = None
    account_type: Optional[str] = None
    account_number_last4: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class DashboardStats(BaseModel):
    total_clients: int
    total_documents: int
    total_transactions: int
    pipeline_status: str
    ml_status: str
    last_processing: Optional[str] = None

# Auth models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None

class UserOut(BaseModel):
    id: str
    username: str
    email: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# Auth models
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    role: str = "user"

class UserOut(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: str = "user"
    created_at: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
