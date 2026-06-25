"""Bank reconciliation domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


class ReconciliationError(Exception):
    """Domain error for reconciliation operations."""


def import_statement(
    db: Session,
    tenant_id: int,
    user_id: int,
    account_id: int,
    statement_balance: Decimal,
    statement_date: date,
    filename: Optional[str] = None,
) -> models.ReconciliationImport:
    """Create a reconciliation import record for a bank statement."""
    ri = models.ReconciliationImport(
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=user_id,
        import_date=date.today(),
        statement_date=statement_date,
        statement_balance=statement_balance,
        filename=filename,
    )
    db.add(ri)
    db.commit()
    db.refresh(ri)
    return ri


def auto_match(
    db: Session,
    import_id: int,
    user_id: int,
    date_window_days: int = 3,
    statement_rows: list[dict] | None = None,
) -> list[dict]:
    """Auto-match imported statement transactions against ledger transactions."""
    ri = db.query(models.ReconciliationImport).filter(
        models.ReconciliationImport.id == import_id,
        models.ReconciliationImport.user_id == user_id,
    ).first()
    if ri is None:
        raise ReconciliationError("Import not found")

    ledger_txns = db.query(models.Transaction).join(models.Statement).filter(
        models.Statement.account_id == ri.account_id,
        models.Transaction.user_id == user_id,
    ).all()

    matches = []
    rows = statement_rows if statement_rows is not None else []
    for stmt_row in rows:
        stmt_amount = Decimal(str(stmt_row.get("amount", 0)))
        stmt_date_raw = stmt_row.get("date")
        if isinstance(stmt_date_raw, str):
            stmt_date = __import__("datetime").date.fromisoformat(stmt_date_raw)
        elif isinstance(stmt_date_raw, date):
            stmt_date = stmt_date_raw
        else:
            stmt_date = None
        best = None
        for txn in ledger_txns:
            if txn.amount is None or txn.date is None:
                continue
            amount_match = abs(Decimal(txn.amount) - stmt_amount) < Decimal("0.01")
            if not amount_match:
                continue
            delta = abs((txn.date - stmt_date).days) if stmt_date else 999
            if delta <= date_window_days:
                if best is None or delta < best["delta"]:
                    best = {"txn": txn, "delta": delta}
        if best:
            m = models.ReconciliationMatch(
                import_id=import_id,
                ledger_tx_id=best["txn"].id,
                statement_tx_id=str(stmt_row.get("id")),
                match_type="auto",
                status="matched",
            )
            db.add(m)
            matches.append({
                "ledger_tx_id": best["txn"].id,
                "statement_tx_id": str(stmt_row.get("id")),
                "match_type": "auto",
            })
    db.commit()
    return matches


def reconciliation_status(db: Session, import_id: int, user_id: int) -> dict:
    """Return cleared balance + outstanding vs statement balance."""
    ri = db.query(models.ReconciliationImport).filter(
        models.ReconciliationImport.id == import_id,
        models.ReconciliationImport.user_id == user_id,
    ).first()
    if ri is None:
        raise ReconciliationError("Import not found")
    matches = db.query(models.ReconciliationMatch).filter(
        models.ReconciliationMatch.import_id == import_id,
    ).all()
    matched_ids = {m.ledger_tx_id for m in matches if m.ledger_tx_id}
    ledger_txns = db.query(models.Transaction).join(models.Statement).filter(
        models.Statement.account_id == ri.account_id,
        models.Transaction.user_id == user_id,
    ).all()
    cleared = sum(
        Decimal(t.amount or 0) for t in ledger_txns
        if t.id in matched_ids
    )
    outstanding = sum(
        Decimal(t.amount or 0) for t in ledger_txns
        if t.id not in matched_ids
    )
    return {
        "statement_balance": float(ri.statement_balance),
        "cleared": float(cleared),
        "outstanding": float(outstanding),
        "difference": float(ri.statement_balance - cleared),
    }
