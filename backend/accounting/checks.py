"""Check register domain logic for TaxFlow Pro v3.11.6 B2.

Tracks physical checks issued: check number, payee, amount, date, account, memo.
- Prevents duplicate check numbers per account.
- Marks checks as cleared/reconciled.
- Searches by check number range.
- Optionally links a check to a transaction.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc, and_

from .. import models


class CheckError(Exception):
    """Domain error for check operations."""


# ---------------------------------------------------------------------------
# Check CRUD
# ---------------------------------------------------------------------------

def record_check(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    check_number: str,
    payee: str,
    amount: Decimal | float | str,
    date_value: date,
    memo: Optional[str] = None,
    transaction_id: Optional[int] = None,
) -> models.Check:
    """Record a new physical check in the register.

    Raises CheckError if:
    - Account doesn't exist or doesn't belong to the tenant.
    - Check number already exists for this account.
    """
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.tenant_id == tenant_id,
        models.Account.user_id == user_id,
    ).first()
    if account is None:
        raise CheckError("Account not found")

    # Duplicate check number guard.
    existing = db.query(models.Check).filter(
        models.Check.account_id == account_id,
        models.Check.check_number == str(check_number),
    ).first()
    if existing is not None:
        raise CheckError(f"Duplicate check number '{check_number}' for account {account_id}")

    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    elif isinstance(amount, str):
        amount = Decimal(amount)

    check = models.Check(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        check_number=str(check_number),
        payee=payee,
        amount=amount,
        date=date_value,
        memo=memo,
        status="pending",
        transaction_id=transaction_id,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def list_checks(
    db: Session,
    tenant_id: int,
    user_id: Optional[int] = None,
    account_id: Optional[int] = None,
    start_number: Optional[str] = None,
    end_number: Optional[str] = None,
    status: Optional[str] = None,
) -> list[models.Check]:
    """List checks, optionally filtered by account, number range, or status."""
    query = db.query(models.Check).filter(models.Check.tenant_id == tenant_id)
    if user_id is not None:
        query = query.filter(models.Check.user_id == user_id)
    if account_id is not None:
        query = query.filter(models.Check.account_id == account_id)
    if start_number is not None:
        query = query.filter(models.Check.check_number >= str(start_number))
    if end_number is not None:
        query = query.filter(models.Check.check_number <= str(end_number))
    if status is not None:
        query = query.filter(models.Check.status == status)
    return query.order_by(asc(models.Check.date), asc(models.Check.id)).all()


def get_check(db: Session, check_id: int, tenant_id: int) -> Optional[models.Check]:
    """Get a single check by ID within a tenant."""
    return db.query(models.Check).filter(
        models.Check.id == check_id,
        models.Check.tenant_id == tenant_id,
    ).first()


def update_check(
    db: Session,
    check_id: int,
    tenant_id: int,
    user_id: int,
    payee: Optional[str] = None,
    amount: Optional[Decimal | float | str] = None,
    date_value: Optional[date] = None,
    memo: Optional[str] = None,
    status: Optional[str] = None,
    transaction_id: Optional[int] = None,
) -> models.Check:
    """Update a check entry."""
    check = db.query(models.Check).filter(
        models.Check.id == check_id,
        models.Check.tenant_id == tenant_id,
        models.Check.user_id == user_id,
    ).first()
    if check is None:
        raise CheckError("Check not found")

    if payee is not None:
        check.payee = payee
    if amount is not None:
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        elif isinstance(amount, str):
            amount = Decimal(amount)
        check.amount = amount
    if date_value is not None:
        check.date = date_value
    if memo is not None:
        check.memo = memo
    if status is not None:
        if status not in ("pending", "cleared", "reconciled", "void"):
            raise CheckError(f"Invalid status '{status}'")
        check.status = status
    if transaction_id is not None:
        check.transaction_id = transaction_id

    db.commit()
    db.refresh(check)
    return check


def mark_cleared(db: Session, check_id: int, tenant_id: int, user_id: int) -> models.Check:
    """Mark a check as cleared."""
    return update_check(db, check_id, tenant_id, user_id, status="cleared")


def mark_reconciled(db: Session, check_id: int, tenant_id: int, user_id: int) -> models.Check:
    """Mark a check as reconciled."""
    return update_check(db, check_id, tenant_id, user_id, status="reconciled")


def void_check(
    db: Session,
    check_id: int,
    tenant_id: int,
    user_id: int,
    reason: Optional[str] = None,
) -> models.Check:
    """Void a check."""
    check = db.query(models.Check).filter(
        models.Check.id == check_id,
        models.Check.tenant_id == tenant_id,
        models.Check.user_id == user_id,
    ).first()
    if check is None:
        raise CheckError("Check not found")
    if check.status == "void":
        raise CheckError("Check already voided")
    check.status = "void"
    if reason:
        check.memo = f"{check.memo or ''} (VOIDED: {reason})".strip()
    db.commit()
    db.refresh(check)
    return check


def delete_check(db: Session, check_id: int, tenant_id: int, user_id: int) -> bool:
    """Delete a check entry."""
    check = db.query(models.Check).filter(
        models.Check.id == check_id,
        models.Check.tenant_id == tenant_id,
        models.Check.user_id == user_id,
    ).first()
    if check is None:
        raise CheckError("Check not found")
    db.delete(check)
    db.commit()
    return True


def search_by_number_range(
    db: Session,
    tenant_id: int,
    account_id: int,
    start: str,
    end: str,
) -> list[models.Check]:
    """Search checks by check number range (inclusive)."""
    return db.query(models.Check).filter(
        models.Check.tenant_id == tenant_id,
        models.Check.account_id == account_id,
        models.Check.check_number >= str(start),
        models.Check.check_number <= str(end),
    ).order_by(asc(models.Check.check_number)).all()


# ---------------------------------------------------------------------------
# Legacy compatibility: issue_check creates a Transaction with tx_type="check".
# New code should use record_check which creates a Check entry.
# ---------------------------------------------------------------------------

def issue_check(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    payee: str,
    amount: Decimal,
    date_value: date,
    memo: Optional[str] = None,
    check_number: Optional[str] = None,
) -> models.Transaction:
    """Issue a new check and create both a Check record and a Transaction.

    This preserves backward compatibility with the existing API while also
    creating a proper Check register entry.
    """
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == user_id,
        models.Account.tenant_id == tenant_id,
    ).first()
    if account is None:
        raise CheckError("Account not found")

    # Determine check number.
    if check_number is None:
        # Auto-assign: find max existing check number for this account.
        existing_checks = db.query(models.Check).filter(
            models.Check.account_id == account_id,
        ).all()
        if existing_checks:
            max_num = max(int(c.check_number) for c in existing_checks if c.check_number.isdigit())
            check_number = str(max_num + 1)
        else:
            check_number = "1001"

    # Check for duplicate.
    existing = db.query(models.Check).filter(
        models.Check.account_id == account_id,
        models.Check.check_number == str(check_number),
    ).first()
    if existing is not None:
        raise CheckError(f"Duplicate check number '{check_number}' for account {account_id}")

    # Find or create synthetic statement for the checking account.
    statement = db.query(models.Statement).filter(
        models.Statement.account_id == account_id,
        models.Statement.filename == "__checks__",
    ).first()
    if statement is None:
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="__checks__",
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)

    txn = models.Transaction(
        statement_id=statement.id,
        tenant_id=tenant_id,
        user_id=user_id,
        date=date_value,
        description=f"Check #{check_number} to {payee}",
        amount=amount,
        tx_type="check",
        category="check",
        workpaper_ref=f"check:{check_number}",
    )
    db.add(txn)
    db.flush()

    # Create the Check record linked to the transaction.
    check = models.Check(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        check_number=str(check_number),
        payee=payee,
        amount=amount,
        date=date_value,
        memo=memo,
        status="pending",
        transaction_id=txn.id,
    )
    db.add(check)
    db.commit()
    db.refresh(txn)
    return txn