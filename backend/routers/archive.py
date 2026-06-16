"""
Archive router: year-end archival of transactions to per-client SQLite files.
- Copy transactions to archive database
- Restore transactions back to main database
"""
import os
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..database import get_db
from .. import models
from .auth import get_current_user

router = APIRouter(prefix="/clients", tags=["archive"])

ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "archive")
MASTER_PASSWORD_ENV = "TAXFLOW_ARCHIVE_MASTER_PASSWORD"


def _archive_db_path(client_id: int, year: int) -> str:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    return os.path.join(ARCHIVE_DIR, f"client_{client_id}_{year}.db")


def _init_archive_schema(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS archived_transactions (
            id INTEGER PRIMARY KEY,
            original_id INTEGER NOT NULL,
            statement_id INTEGER,
            tenant_id INTEGER NOT NULL,
            client_id INTEGER,
            date TEXT,
            description TEXT,
            amount REAL,
            tx_type TEXT,
            category TEXT DEFAULT 'uncategorized',
            running_balance REAL,
            confirmed INTEGER DEFAULT 0,
            is_manual INTEGER DEFAULT 0,
            is_journal INTEGER DEFAULT 0,
            tax_line TEXT,
            source_pdf_path TEXT,
            created_at TEXT,
            updated_at TEXT,
            archived_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _copy_transactions_to_archive(
    db_path: str, transactions: list
):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for tx in transactions:
        cursor.execute(
            """
            INSERT OR REPLACE INTO archived_transactions
            (original_id, statement_id, tenant_id, client_id, date, description,
             amount, tx_type, category, running_balance, confirmed, is_manual,
             is_journal, tax_line, source_pdf_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.id, tx.statement_id, tx.tenant_id, tx.client_id,
                tx.date, tx.description,
                float(tx.amount) if tx.amount is not None else None,
                tx.tx_type, tx.category,
                float(tx.running_balance) if tx.running_balance is not None else None,
                1 if tx.confirmed else 0,
                1 if tx.is_manual else 0,
                1 if tx.is_journal else 0,
                tx.tax_line, tx.source_pdf_path,
                tx.created_at.isoformat() if tx.created_at else None,
                tx.updated_at.isoformat() if tx.updated_at else None,
            ),
        )
    conn.commit()
    conn.close()


def _read_transactions_from_archive(db_path: str) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT original_id, statement_id, tenant_id, client_id, date,
               description, amount, tx_type, category, running_balance,
               confirmed, is_manual, is_journal, tax_line, source_pdf_path,
               created_at, updated_at
        FROM archived_transactions
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post(
    "/{client_id}/archive-year",
    status_code=status.HTTP_200_OK,
    summary="Archive all transactions for a client year",
)
def archive_year(
    client_id: int,
    year: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    transactions = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.client_id == client_id,
            models.Transaction.date >= year_start,
            models.Transaction.date <= year_end,
            models.Transaction.archived == False,
        )
        .all()
    )

    if not transactions:
        raise HTTPException(
            status_code=404, detail="No unarchived transactions found for this year"
        )

    db_path = _archive_db_path(client_id, year)
    _init_archive_schema(db_path)
    _copy_transactions_to_archive(db_path, transactions)

    for tx in transactions:
        tx.archived = True

    db.commit()

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="archive_year",
        entity_type="client",
        entity_id=client_id,
        details=f"Archived {len(transactions)} transactions for year {year}",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Archived {len(transactions)} transactions for year {year}",
        "archive_path": db_path,
        "count": len(transactions),
    }


@router.post(
    "/{client_id}/restore-year",
    status_code=status.HTTP_200_OK,
    summary="Restore archived transactions for a client year",
)
def restore_year(
    client_id: int,
    year: int,
    master_password: str = Form(..., description="Master password for restore verification"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    expected = os.environ.get(MASTER_PASSWORD_ENV)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Archive master password not configured",
        )
    if master_password != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid master password",
        )

    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    db_path = _archive_db_path(client_id, year)
    if not os.path.exists(db_path):
        raise HTTPException(
            status_code=404, detail=f"No archive found for client {client_id} year {year}"
        )

    archived = _read_transactions_from_archive(db_path)
    if not archived:
        raise HTTPException(
            status_code=404, detail="Archive file contains no transactions"
        )

    restored_count = 0
    for row in archived:
        tx = (
            db.query(models.Transaction)
            .filter(models.Transaction.id == row["original_id"])
            .first()
        )
        if tx:
            tx.archived = False
            restored_count += 1

    db.commit()

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="restore_year",
        entity_type="client",
        entity_id=client_id,
        details=f"Restored {restored_count} transactions for year {year}",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Restored {restored_count} transactions for year {year}",
        "count": restored_count,
    }
