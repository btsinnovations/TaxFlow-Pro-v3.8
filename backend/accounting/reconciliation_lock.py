"""Reconciliation locking for TaxFlow Pro v3.11.6 R3.

Prevents modifications to completed reconciliations and their cleared transactions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


class ReconciliationLockError(Exception):
    """Domain error for reconciliation lock operations."""


def complete_reconciliation(
    db: Session,
    import_id: int,
    user_id: int,
    tenant_id: int,
    profile_id: Optional[int] = None,
    allow_unbalanced: bool = False,
) -> models.ReconciliationImport:
    """Complete a reconciliation — lock it from further modifications."""
    imp = db.query(models.ReconciliationImport).filter(
        models.ReconciliationImport.id == import_id,
        models.ReconciliationImport.tenant_id == tenant_id,
    ).first()
    if imp is None:
        raise ReconciliationLockError("Reconciliation import not found")
    if imp.is_completed:
        raise ReconciliationLockError("Reconciliation already completed")

    # Check difference is zero (unless allow_unbalanced)
    if not allow_unbalanced:
        matches = db.query(models.ReconciliationMatch).filter(
            models.ReconciliationMatch.import_id == import_id,
            models.ReconciliationMatch.status == "matched",
        ).all()
        ledger_total = Decimal("0")
        for m in matches:
            txn = db.query(models.Transaction).filter(
                models.Transaction.id == m.ledger_tx_id,
            ).first()
            if txn:
                ledger_total += Decimal(str(txn.amount or 0))
        if ledger_total != Decimal(str(imp.statement_balance or 0)):
            raise ReconciliationLockError(
                f"Reconciliation difference is non-zero "
                f"(ledger={ledger_total}, statement={imp.statement_balance})"
            )

    # Snapshot cleared transaction IDs
    cleared_txns = db.query(models.ReconciliationMatch).filter(
        models.ReconciliationMatch.import_id == import_id,
        models.ReconciliationMatch.status == "matched",
    ).all()
    cleared_ids = [m.ledger_tx_id for m in cleared_txns if m.ledger_tx_id]

    imp.is_completed = True
    imp.completed_at = datetime.now(timezone.utc)
    imp.completed_by_profile_id = profile_id

    db.commit()
    db.refresh(imp)
    return imp


def reopen_reconciliation(
    db: Session,
    import_id: int,
    user_id: int,
    tenant_id: int,
) -> models.ReconciliationImport:
    """Reopen a completed reconciliation."""
    imp = db.query(models.ReconciliationImport).filter(
        models.ReconciliationImport.id == import_id,
        models.ReconciliationImport.tenant_id == tenant_id,
    ).first()
    if imp is None:
        raise ReconciliationLockError("Reconciliation import not found")
    if not imp.is_completed:
        raise ReconciliationLockError("Reconciliation is not completed")

    imp.is_completed = False
    imp.completed_at = None
    imp.completed_by_profile_id = None

    db.commit()
    db.refresh(imp)
    return imp


def is_reconciliation_completed(db: Session, import_id: int) -> bool:
    """Check if a reconciliation import is completed."""
    imp = db.query(models.ReconciliationImport).filter(
        models.ReconciliationImport.id == import_id,
    ).first()
    return imp is not None and imp.is_completed == True


def is_transaction_cleared(db: Session, transaction_id: int) -> Optional[int]:
    """Check if a transaction is cleared by any completed reconciliation.

    Returns the reconciliation import ID if cleared, None otherwise.
    """
    match = db.query(models.ReconciliationMatch).filter(
        models.ReconciliationMatch.ledger_tx_id == transaction_id,
        models.ReconciliationMatch.status == "matched",
    ).first()
    if match is None:
        return None
    imp = db.query(models.ReconciliationImport).filter(
        models.ReconciliationImport.id == match.import_id,
        models.ReconciliationImport.is_completed == True,
    ).first()
    if imp is None:
        return None
    return imp.id