from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str
    keyfile_path: Optional[str] = None

class LocalLogin(BaseModel):
    username: str
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
    created_at: datetime
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
