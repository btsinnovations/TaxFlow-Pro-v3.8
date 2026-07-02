"""Unified register domain helpers for TaxFlow Pro v3.11.03.

Provides list/update/delete operations plus running-balance computation for
bank and GL account registers. All functions operate within the caller's
session/tenant context to preserve existing v3.10 auth and RLS patterns.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import asc
from sqlalchemy.orm import Session

from backend import models


class RegisterError(Exception):
    """Domain-level register error."""

    pass


def list_transactions(
    db: Session,
    tenant_id: int,
    filters: Optional[Dict[str, Any]] = None,
) -> List[models.Transaction]:
    """Return transactions ordered by date, then id, for a tenant.

    ``filters`` is an optional dict that may contain:
      - account_id: filter by account_id (statement.account_id)
      - user_id: filter by transaction owner
      - start_date / end_date: inclusive date range
      - category: exact category match
      - gl_account_id: exact GL account match
      - q: case-insensitive substring search on description
      - limit / offset: offset pagination (defaults 500, 0)
      - after_date / after_id: keyset pagination overrides (both required together)
    """
    filters = filters or {}
    query = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
    )

    account_id = filters.get("account_id")
    if account_id is not None:
        query = query.join(models.Statement).filter(
            models.Statement.account_id == account_id,
        )

    user_id = filters.get("user_id")
    if user_id is not None:
        query = query.filter(models.Transaction.user_id == user_id)

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    if start_date is not None:
        query = query.filter(models.Transaction.date >= start_date)
    if end_date is not None:
        query = query.filter(models.Transaction.date <= end_date)

    category = filters.get("category")
    if category is not None:
        query = query.filter(models.Transaction.category == category)

    gl_account_id = filters.get("gl_account_id")
    if gl_account_id is not None:
        query = query.filter(models.Transaction.gl_account_id == gl_account_id)

    q = filters.get("q")
    if q:
        query = query.filter(models.Transaction.description.ilike(f"%{q}%"))

    # Prefer keyset pagination when both after_date and after_id are provided.
    after_date = filters.get("after_date")
    after_id = filters.get("after_id")
    if after_date is not None and after_id is not None:
        query = query.filter(
            ((models.Transaction.date == after_date) & (models.Transaction.id > after_id))
            | (models.Transaction.date > after_date)
        )
        query = query.order_by(asc(models.Transaction.date), asc(models.Transaction.id))
        limit = filters.get("limit", 500)
        if limit is not None:
            query = query.limit(int(limit))
    else:
        query = query.order_by(asc(models.Transaction.date), asc(models.Transaction.id))
        limit = filters.get("limit", 500)
        offset = filters.get("offset", 0)
        if limit is not None:
            query = query.limit(int(limit))
        if offset:
            query = query.offset(int(offset))

    return query.all()


def _decimal(value: Any) -> Optional[Decimal]:
    """Convert a value to Decimal or None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def update_transaction(
    db: Session,
    transaction_id: int,
    tenant_id: int,
    user_id: int,
    description: Optional[str] = None,
    amount: Optional[Any] = None,
    date_value: Optional[date] = None,
    category: Optional[str] = None,
    gl_account_id: Optional[int] = None,
) -> models.Transaction:
    """Update an existing transaction's editable register fields."""
    tx = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == user_id,
        )
        .first()
    )
    if tx is None:
        raise RegisterError("Transaction not found")

    if description is not None:
        tx.description = description
    if amount is not None:
        tx.amount = _decimal(amount)
    if date_value is not None:
        tx.date = date_value
    if category is not None:
        tx.category = category
    if gl_account_id is not None:
        tx.gl_account_id = gl_account_id

    db.commit()
    db.refresh(tx)
    return tx


def delete_transaction(
    db: Session,
    transaction_id: int,
    tenant_id: int,
    user_id: int,
) -> bool:
    """Delete a transaction if it exists and belongs to the tenant/user."""
    tx = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == user_id,
        )
        .first()
    )
    if tx is None:
        raise RegisterError("Transaction not found")
    db.delete(tx)
    db.commit()
    return True


def compute_running_balance(
    db: Session,
    account_id: int,
    opening_balance: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Compute running balance rows for an account ordered by date/id.

    ``opening_balance`` defaults to the account's most recent statement
    opening_balance if available, otherwise 0. Returns a list of dicts with
    the transaction plus ``running_balance`` in float form for JSON serialization.
    """
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if account is None:
        raise RegisterError("Account not found")

    if opening_balance is None:
        latest_statement = (
            db.query(models.Statement)
            .filter(models.Statement.account_id == account_id)
            .order_by(models.Statement.period_start.desc())
            .first()
        )
        opening_balance = (
            latest_statement.opening_balance
            if latest_statement and latest_statement.opening_balance is not None
            else Decimal("0.00")
        )
    else:
        opening_balance = _decimal(opening_balance) or Decimal("0.00")

    transactions = (
        db.query(models.Transaction)
        .join(models.Statement)
        .filter(
            models.Statement.account_id == account_id,
        )
        .order_by(asc(models.Transaction.date), asc(models.Transaction.id))
        .all()
    )

    running = Decimal(opening_balance)
    rows: List[Dict[str, Any]] = []
    for tx in transactions:
        amount = _decimal(tx.amount) or Decimal("0.00")
        # For depository accounts, "credit" in bank statement terms is money
        # leaving the account; everything else increases the balance.
        if tx.tx_type and tx.tx_type.lower() == "credit":
            running -= amount
        else:
            running += amount

        rows.append(
            {
                "id": tx.id,
                "date": tx.date.isoformat() if tx.date else None,
                "description": tx.description,
                "amount": float(amount),
                "tx_type": tx.tx_type,
                "category": tx.category,
                "running_balance": float(running),
                "statement_id": tx.statement_id,
                "gl_account_id": tx.gl_account_id,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
        )

    return rows
