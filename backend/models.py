from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey
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
    statements = relationship("Statement", back_populates="owner")

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String)
    tax_id = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="clients")
    accounts = relationship("Account", back_populates="client")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    institution = Column(String)
    account_number_masked = Column(String)
    type = Column(String, default="checking")
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    owner = relationship("User", back_populates="accounts")
    client = relationship("Client", back_populates="accounts")
    statements = relationship("Statement", back_populates="account")

class Statement(Base):
    __tablename__ = "statements"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
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
    owner = relationship("User", back_populates="statements")
    transactions = relationship("Transaction", back_populates="statement")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"))
    date = Column(String)
    description = Column(String)
    amount = Column(Numeric(12, 2))
    tx_type = Column(String)
    category = Column(String, default="uncategorized")
    running_balance = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    statement = relationship("Statement", back_populates="transactions")
