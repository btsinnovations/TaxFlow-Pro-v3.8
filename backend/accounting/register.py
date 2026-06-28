"""Unified register domain helpers for TaxFlow Pro v3.11.6 B2.

Provides list/update/delete operations plus running-balance computation for
bank and GL account registers. All functions operate within the caller's
session/tenant context to preserve existing v3.10 auth and RLS patterns.

B2 enhancements:
- Filters: date range, account, amount range, description search, tags, reconciled status.
- Sort by date, amount, description, account.
- Pagination (offset/limit) + cursor option for large datasets.
- Inline status: cleared, reconciled, pending.
- Bulk operations: delete, tag, change status.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session

from backend import models


class RegisterError(Exception):
    """Domain-level register error."""

    pass


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

VALID_STATUSES = {"pending", "cleared", "reconciled"}


def set_transaction_status(
    db: Session,
    transaction_id: int,
    tenant_id: int,
    user_id: int,
    status: str,
) -> models.Transaction:
    """Set the status (pending/cleared/reconciled) on a transaction."""
    if status not in VALID_STATUSES:
        raise RegisterError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
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
    tx.status = status
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------

def add_tags(
    db: Session,
    transaction_id: int,
    tenant_id: int,
    user_id: int,
    tags: list[str],
) -> models.Transaction:
    """Add tags to a transaction (comma-separated in the tags column)."""
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
    existing = {t.strip() for t in (tx.tags or "").split(",") if t.strip()}
    existing.update(tags)
    tx.tags = ",".join(sorted(existing))
    db.commit()
    db.refresh(tx)
    return tx


def remove_tags(
    db: Session,
    transaction_id: int,
    tenant_id: int,
    user_id: int,
    tags: list[str],
) -> models.Transaction:
    """Remove tags from a transaction."""
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
    existing = {t.strip() for t in (tx.tags or "").split(",") if t.strip()}
    existing -= set(tags)
    tx.tags = ",".join(sorted(existing))
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# List with enhanced filters, sort, pagination
# ---------------------------------------------------------------------------

SORTABLE_FIELDS = {
    "date": models.Transaction.date,
    "amount": models.Transaction.amount,
    "description": models.Transaction.description,
    "account": models.Account.name,
}


def list_transactions(
    db: Session,
    tenant_id: int,
    filters: Optional[Dict[str, Any]] = None,
) -> List[models.Transaction]:
    """Return transactions for a tenant with enhanced filtering, sorting, and pagination.

    ``filters`` is an optional dict that may contain:
      - account_id: filter by account_id (statement.account_id)
      - user_id: filter by transaction owner
      - start_date / end_date: inclusive date range
      - category: exact category match
      - gl_account_id: exact GL account match
      - coa_account_id: exact COA account match
      - q: case-insensitive substring search on description
      - min_amount / max_amount: amount range filter
      - tags: list of tags to filter by (any match)
      - status: filter by transaction status (pending/cleared/reconciled)
      - sort_by: field to sort by (date, amount, description, account)
      - sort_order: "asc" or "desc" (default: asc)
      - limit / offset: pagination (defaults 500, 0)
      - cursor: optional cursor for cursor-based pagination (dict with last_date and last_id)
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

    coa_account_id = filters.get("coa_account_id")
    if coa_account_id is not None:
        query = query.filter(models.Transaction.coa_account_id == coa_account_id)

    q = filters.get("q")
    if q:
        query = query.filter(models.Transaction.description.ilike(f"%{q}%"))

    min_amount = filters.get("min_amount")
    max_amount = filters.get("max_amount")
    if min_amount is not None:
        query = query.filter(models.Transaction.amount >= Decimal(str(min_amount)))
    if max_amount is not None:
        query = query.filter(models.Transaction.amount <= Decimal(str(max_amount)))

    # Tag filtering: match any of the provided tags.
    tags = filters.get("tags")
    if tags:
        tag_conditions = []
        for tag in tags:
            # Comma-separated tags: use LIKE to match within the string.
            tag_conditions.append(models.Transaction.tags.ilike(f"%{tag}%"))
        query = query.filter(or_(*tag_conditions))

    # Status filter.
    status_filter = filters.get("status")
    if status_filter is not None:
        query = query.filter(models.Transaction.status == status_filter)

    # Sorting.
    sort_by = filters.get("sort_by", "date")
    sort_order = filters.get("sort_order", "asc")
    sort_column = SORTABLE_FIELDS.get(sort_by, models.Transaction.date)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column), desc(models.Transaction.id))
    else:
        query = query.order_by(asc(sort_column), asc(models.Transaction.id))

    # Cursor-based pagination: if cursor is provided, use it instead of offset.
    cursor = filters.get("cursor")
    if cursor:
        cursor_date = cursor.get("last_date")
        cursor_id = cursor.get("last_id")
        if cursor_date is not None and cursor_id is not None:
            if sort_order == "desc":
                query = query.filter(
                    or_(
                        models.Transaction.date < cursor_date,
                        (models.Transaction.date == cursor_date) & (models.Transaction.id < cursor_id),
                    )
                )
            else:
                query = query.filter(
                    or_(
                        models.Transaction.date > cursor_date,
                        (models.Transaction.date == cursor_date) & (models.Transaction.id > cursor_id),
                    )
                )

    limit = filters.get("limit", 500)
    offset = filters.get("offset", 0)
    if limit is not None:
        query = query.limit(int(limit))
    if offset and not cursor:
        query = query.offset(int(offset))

    return query.all()


def list_transactions_with_meta(
    db: Session,
    tenant_id: int,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return transactions with pagination metadata.

    Returns a dict with:
      - items: list of Transaction objects
      - total: total count (before pagination)
      - limit: page size
      - offset: current offset
      - next_cursor: cursor for next page (or None)
    """
    filters = filters or {}
    limit = int(filters.get("limit", 500))
    offset = int(filters.get("offset", 0))

    # Get total count (without limit/offset/cursor).
    count_query = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
    )

    account_id = filters.get("account_id")
    if account_id is not None:
        count_query = count_query.join(models.Statement).filter(
            models.Statement.account_id == account_id,
        )

    user_id = filters.get("user_id")
    if user_id is not None:
        count_query = count_query.filter(models.Transaction.user_id == user_id)

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    if start_date is not None:
        count_query = count_query.filter(models.Transaction.date >= start_date)
    if end_date is not None:
        count_query = count_query.filter(models.Transaction.date <= end_date)

    q = filters.get("q")
    if q:
        count_query = count_query.filter(models.Transaction.description.ilike(f"%{q}%"))

    min_amount = filters.get("min_amount")
    max_amount = filters.get("max_amount")
    if min_amount is not None:
        count_query = count_query.filter(models.Transaction.amount >= Decimal(str(min_amount)))
    if max_amount is not None:
        count_query = count_query.filter(models.Transaction.amount <= Decimal(str(max_amount)))

    status_filter = filters.get("status")
    if status_filter is not None:
        count_query = count_query.filter(models.Transaction.status == status_filter)

    total = count_query.count()

    items = list_transactions(db, tenant_id, filters)

    # Build next cursor.
    next_cursor = None
    if len(items) == limit and limit > 0:
        last = items[-1] if items else None
        if last:
            next_cursor = {
                "last_date": last.date.isoformat() if last.date else None,
                "last_id": last.id,
            }

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_cursor": next_cursor,
    }


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
    coa_account_id: Optional[int] = None,
    tags: Optional[str] = None,
    status: Optional[str] = None,
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
    if coa_account_id is not None:
        tx.coa_account_id = coa_account_id
    if tags is not None:
        tx.tags = tags
    if status is not None:
        if status not in VALID_STATUSES:
            raise RegisterError(f"Invalid status '{status}'")
        tx.status = status

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


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

def bulk_delete(
    db: Session,
    transaction_ids: List[int],
    tenant_id: int,
    user_id: int,
) -> int:
    """Delete multiple transactions. Returns the count deleted."""
    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id.in_(transaction_ids),
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == user_id,
        )
        .all()
    )
    for tx in txs:
        db.delete(tx)
    db.commit()
    return len(txs)


def bulk_tag(
    db: Session,
    transaction_ids: List[int],
    tenant_id: int,
    user_id: int,
    tags: List[str],
) -> int:
    """Add tags to multiple transactions. Returns the count updated."""
    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id.in_(transaction_ids),
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == user_id,
        )
        .all()
    )
    for tx in txs:
        existing = {t.strip() for t in (tx.tags or "").split(",") if t.strip()}
        existing.update(tags)
        tx.tags = ",".join(sorted(existing))
    db.commit()
    return len(txs)


def bulk_change_status(
    db: Session,
    transaction_ids: List[int],
    tenant_id: int,
    user_id: int,
    status: str,
) -> int:
    """Change status on multiple transactions. Returns the count updated."""
    if status not in VALID_STATUSES:
        raise RegisterError(f"Invalid status '{status}'")
    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id.in_(transaction_ids),
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == user_id,
        )
        .all()
    )
    for tx in txs:
        tx.status = status
    db.commit()
    return len(txs)


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
                "coa_account_id": tx.coa_account_id,
                "status": tx.status or "pending",
                "tags": tx.tags or "",
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
        )

    return rows