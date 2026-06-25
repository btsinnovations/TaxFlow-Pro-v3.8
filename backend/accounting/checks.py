"""Check register domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc

from .. import models


class CheckError(Exception):
    """Domain error for check operations."""


def issue_check(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    payee: str,
    amount: Decimal,
    date_value: date,
    memo: Optional[str] = None,
) -> models.Transaction:
    """Issue a new check and allocate the next check number for the account."""
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == user_id,
        models.Account.tenant_id == tenant_id,
    ).first()
    if account is None:
        raise CheckError("Account not found")

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

    max_check = db.query(models.Transaction).filter(
        models.Transaction.statement_id == statement.id,
    ).count()
    check_number = max_check + 1001  # Start check numbering at 1001

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
    db.commit()
    db.refresh(txn)
    return txn


def list_checks(db: Session, account_id: int, user_id: int) -> list[models.Transaction]:
    """Return check transactions for a checking account."""
    return db.query(models.Transaction).join(models.Statement).filter(
        models.Statement.account_id == account_id,
        models.Transaction.user_id == user_id,
        models.Transaction.tx_type == "check",
    ).order_by(asc(models.Transaction.date), asc(models.Transaction.id)).all()


def void_check(db: Session, transaction_id: int, user_id: int, reason: Optional[str] = None) -> models.Transaction:
    """Void a check by flipping its type and appending a reason."""
    txn = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == user_id,
    ).first()
    if txn is None:
        raise CheckError("Check not found")
    if txn.tx_type == "void":
        raise CheckError("Check already voided")
    txn.tx_type = "void"
    txn.description = f"{txn.description or ''} (VOIDED: {reason or 'no reason'})"
    db.commit()
    db.refresh(txn)
    return txn
