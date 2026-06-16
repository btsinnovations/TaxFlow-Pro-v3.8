"""
Journal Entry router for TaxFlow Pro v3.8.

Provides full CRUD for journal entries with line-item support,
debit/credit validation, posting to transactions, period lock
checks, and tamper-evident audit trail entries.
"""

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id
from ..audit.audit_trail import (
    create_audit_entry,
    ACTION_CREATE_JOURNAL,
    ACTION_UPDATE_JOURNAL,
    ACTION_DELETE_JOURNAL,
    ACTION_POST_JOURNAL,
)
from .auth import get_current_user

router = APIRouter(prefix="/journal-entries", tags=["journal-entries"])


def _wrap_tenant(request: Request, db: Session) -> None:
    """Set RLS tenant context when X-Tenant-ID header is present on PostgreSQL."""
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


def _get_tenant_id(request: Request, client_id: int) -> int:
    """Resolve tenant_id from request state or fall back to client_id."""
    tenant_id = getattr(request.state, "tenant_id", None)
    return tenant_id if tenant_id is not None else client_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_balance(lines: List[schemas.JournalEntryLineCreate]) -> None:
    """Ensure total debits equal total credits across all lines."""
    total_debits = sum(Decimal(str(line.debit)) for line in lines)
    total_credits = sum(Decimal(str(line.credit)) for line in lines)
    if total_debits != total_credits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Debits ({float(total_debits):.2f}) must equal credits ({float(total_credits):.2f})",
        )
    if total_debits == Decimal("0") and total_credits == Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry must have at least one non-zero line.",
        )


def _check_period_not_locked(
    db: Session, tenant_id: int, entry_date: str, user_id: int
) -> None:
    """Raise HTTPException if entry_date falls within a locked period."""
    # Extract year from entry_date (format: YYYY-MM-DD)
    year = entry_date[:4] if entry_date and len(entry_date) >= 4 else None
    if not year:
        return

    locked_period = (
        db.query(models.Period)
        .filter(
            models.Period.tenant_id == tenant_id,
            models.Period.is_locked == True,
            models.Period.start_date <= entry_date,
            models.Period.end_date >= entry_date,
        )
        .first()
    )
    if locked_period:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entry date {entry_date} falls within locked period '{locked_period.name}' ({locked_period.start_date} to {locked_period.end_date}).",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=schemas.JournalEntry, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    request: Request,
    je_data: schemas.JournalEntryCreate,
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a new journal entry with line items.
    *client_id* query param is required to set tenant scoping.
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    if not je_data.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Journal entry must have at least one line item.",
        )

    _validate_balance(je_data.lines)
    _check_period_not_locked(db, tenant_id, je_data.entry_date, current_user.id)

    db_je = models.JournalEntry(
        entry_number=je_data.entry_number,
        entry_date=je_data.entry_date,
        memo=je_data.memo,
        source=je_data.source,
        tenant_id=tenant_id,
        user_id=current_user.id,
    )
    db.add(db_je)
    db.flush()

    for line in je_data.lines:
        db_line = models.JournalEntryLine(
            journal_entry_id=db_je.id,
            tenant_id=tenant_id,
            account_code=line.account_code,
            account_name=line.account_name,
            debit=line.debit,
            credit=line.credit,
            memo=line.memo,
        )
        db.add(db_line)

    db.commit()
    db.refresh(db_je)

    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_CREATE_JOURNAL,
        entity_type="JournalEntry",
        entity_id=db_je.id,
        new_values={
            "entry_number": je_data.entry_number,
            "entry_date": je_data.entry_date,
            "memo": je_data.memo,
            "line_count": len(je_data.lines),
        },
        client_id=tenant_id,
    )
    db.commit()

    return db_je


@router.get("/", response_model=List[schemas.JournalEntry])
def list_journal_entries(
    request: Request,
    client_id: int,
    skip: int = 0,
    limit: int = 100,
    posted_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List journal entries for a client.  *client_id* is required."""
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    query = db.query(models.JournalEntry).filter(
        models.JournalEntry.tenant_id == tenant_id,
        models.JournalEntry.user_id == current_user.id,
    )

    if posted_only:
        # A JE is considered "posted" if it has associated transactions
        query = query.filter(
            models.JournalEntry.id.in_(
                db.query(models.Transaction.journal_entry_id)
                .filter(models.Transaction.journal_entry_id.isnot(None))
                .distinct()
            )
        )

    return (
        query.order_by(models.JournalEntry.entry_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{je_id}", response_model=schemas.JournalEntry)
def get_journal_entry(
    request: Request,
    je_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get a single journal entry including its line items."""
    _wrap_tenant(request, db)
    je = (
        db.query(models.JournalEntry)
        .filter(
            models.JournalEntry.id == je_id,
            models.JournalEntry.user_id == current_user.id,
        )
        .first()
    )
    if not je:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return je


@router.post("/{je_id}/post", response_model=schemas.JournalEntry)
def post_journal_entry(
    request: Request,
    je_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Post a journal entry: create a Transaction for each line,
    mark the JE as posted, and write audit entries.

    - JE must not already be posted.
    - Debits/credits must balance.
    - Target period must not be locked.
    """
    _wrap_tenant(request, db)
    je = (
        db.query(models.JournalEntry)
        .filter(
            models.JournalEntry.id == je_id,
            models.JournalEntry.user_id == current_user.id,
        )
        .first()
    )
    if not je:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    # Check if already posted (has transactions linked)
    existing_tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.journal_entry_id == je_id)
        .first()
    )
    if existing_tx is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Journal entry is already posted.",
        )

    # Validate balance
    _validate_balance(
        [schemas.JournalEntryLineCreate.model_validate(line) for line in je.lines]
    )

    # Check period not locked
    _check_period_not_locked(db, je.tenant_id, je.entry_date, current_user.id)

    # Need a dummy statement_id for transactions.  Find or create a placeholder
    # statement linked to the JE's tenant.
    statement = (
        db.query(models.Statement)
        .filter(models.Statement.tenant_id == je.tenant_id)
        .first()
    )
    if statement is None:
        # Find an account for this tenant to create a statement
        account = (
            db.query(models.Account)
            .filter(models.Account.tenant_id == je.tenant_id)
            .first()
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No account found for this client. Create an account first.",
            )
        statement = models.Statement(
            account_id=account.id,
            tenant_id=je.tenant_id,
            user_id=current_user.id,
            filename="journal-entry-posting",
            period_start=je.entry_date,
            period_end=je.entry_date,
        )
        db.add(statement)
        db.flush()

    # Create one Transaction per JE line
    for line in je.lines:
        # Debit = +amount, Credit = -amount
        amount = Decimal(str(line.debit)) - Decimal(str(line.credit))
        tx = models.Transaction(
            statement_id=statement.id,
            tenant_id=je.tenant_id,
            client_id=je.tenant_id,
            journal_entry_id=je.id,
            date=je.entry_date,
            description=f"JE {je.entry_number} - {line.account_code} {line.account_name or ''}",
            amount=float(abs(amount)),
            tx_type="debit" if amount > 0 else "credit",
            category="journal",
            confirmed=True,
            is_manual=True,
            is_journal=True,
        )
        db.add(tx)

    db.commit()
    db.refresh(je)

    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_POST_JOURNAL,
        entity_type="JournalEntry",
        entity_id=je.id,
        new_values={
            "entry_number": je.entry_number,
            "lines_posted": len(je.lines),
        },
        client_id=je.tenant_id,
    )
    db.commit()

    return je


@router.delete("/{je_id}")
def delete_journal_entry(
    request: Request,
    je_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Delete a journal entry only if it has **not** been posted.
    Posted JEs have linked transactions and cannot be deleted.
    """
    _wrap_tenant(request, db)
    je = (
        db.query(models.JournalEntry)
        .filter(
            models.JournalEntry.id == je_id,
            models.JournalEntry.user_id == current_user.id,
        )
        .first()
    )
    if not je:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    # Check if posted
    posted_tx = (
        db.query(models.Transaction)
        .filter(models.Transaction.journal_entry_id == je_id)
        .first()
    )
    if posted_tx is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a posted journal entry. Reverse it instead.",
        )

    entry_number = je.entry_number
    tenant_id = je.tenant_id
    je_id_for_audit = je.id

    db.delete(je)
    db.commit()

    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_DELETE_JOURNAL,
        entity_type="JournalEntry",
        entity_id=je_id_for_audit,
        old_values={"entry_number": entry_number},
        client_id=tenant_id,
    )
    db.commit()

    return {"ok": True, "detail": f"Journal entry {entry_number} deleted."}
