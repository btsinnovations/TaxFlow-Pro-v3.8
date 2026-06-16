<<<<<<< HEAD
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey
=======
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Index
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
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
    created_at = Column(DateTime, server_default=func.now())
    clients = relationship("Client", back_populates="owner")
    accounts = relationship("Account", back_populates="owner")
<<<<<<< HEAD
    statements = relationship("Statement", back_populates="owner")
=======
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String)
    tax_id = Column(String)
<<<<<<< HEAD
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="clients")
    accounts = relationship("Account", back_populates="client")

class Account(Base):
    __tablename__ = "accounts"
=======
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="clients")
    accounts = relationship("Account", foreign_keys="Account.client_id", back_populates="client")

class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_accounts_tenant_id", "tenant_id"),
    )
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    institution = Column(String)
    account_number_masked = Column(String)
    type = Column(String, default="checking")
<<<<<<< HEAD
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="accounts")
    client = relationship("Client", back_populates="accounts")
=======
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="accounts")
    client = relationship("Client", foreign_keys=[client_id], back_populates="accounts")
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    statements = relationship("Statement", back_populates="account")

class Statement(Base):
    __tablename__ = "statements"
<<<<<<< HEAD
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
=======
    __table_args__ = (
        Index("ix_statements_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
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
<<<<<<< HEAD
    owner = relationship("User", back_populates="statements")
=======
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    transactions = relationship("Transaction", back_populates="statement")

class Transaction(Base):
    __tablename__ = "transactions"
<<<<<<< HEAD
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"))
=======
    __table_args__ = (
        Index("ix_transactions_tenant_id", "tenant_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    date = Column(String)
    description = Column(String)
    amount = Column(Numeric(12, 2))
    tx_type = Column(String)
    category = Column(String, default="uncategorized")
    running_balance = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    statement = relationship("Statement", back_populates="transactions")
