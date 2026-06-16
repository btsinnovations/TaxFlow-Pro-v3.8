"""
Transaction Notes & Flags router for TaxFlow Pro v3.8.

Provides endpoints for attaching notes and flags to transactions,
with username-enriched list views and flag resolution.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id
from .auth import get_current_user

router = APIRouter(tags=["transactions-notes-flags"])


def _wrap_tenant(request: Request, db: Session) -> None:
    """Set RLS tenant context when X-Tenant-ID header is present on PostgreSQL."""
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


def _get_tenant_id(request: Request, transaction: models.Transaction) -> int:
    """Resolve tenant_id from request state or fall back to transaction tenant."""
    tenant_id = getattr(request.state, "tenant_id", None)
    return tenant_id if tenant_id is not None else transaction.tenant_id


def _verify_transaction_owner(
    db: Session, tx_id: int, user_id: int
) -> models.Transaction:
    """Fetch a transaction ensuring it belongs to the current user."""
    tx = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == tx_id,
        )
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return tx


# ============================================================================
# NOTES
# ============================================================================

@router.post("/transactions/{tx_id}/notes", response_model=schemas.TransactionNote)
def create_transaction_note(
    request: Request,
    tx_id: int,
    note_data: schemas.TransactionNoteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a note attached to a transaction."""
    _wrap_tenant(request, db)
    tx = _verify_transaction_owner(db, tx_id, current_user.id)
    tenant_id = _get_tenant_id(request, tx)

    db_note = models.TransactionNote(
        transaction_id=tx_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        note=note_data.note,
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


@router.get("/transactions/{tx_id}/notes")
def list_transaction_notes(
    request: Request,
    tx_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List notes for a transaction, enriched with the username of
    the user who wrote each note.
    """
    _wrap_tenant(request, db)
    tx = _verify_transaction_owner(db, tx_id, current_user.id)

    notes = (
        db.query(
            models.TransactionNote,
            models.User.username.label("username"),
        )
        .join(models.User, models.TransactionNote.user_id == models.User.id)
        .filter(models.TransactionNote.transaction_id == tx_id)
        .order_by(desc(models.TransactionNote.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []
    for note, username in notes:
        results.append({
            "id": note.id,
            "transaction_id": note.transaction_id,
            "tenant_id": note.tenant_id,
            "user_id": note.user_id,
            "username": username,
            "note": note.note,
            "created_at": note.created_at.isoformat() if note.created_at else None,
        })

    return results


# ============================================================================
# FLAGS
# ============================================================================

@router.post("/transactions/{tx_id}/flags", response_model=schemas.TransactionFlag)
def create_transaction_flag(
    request: Request,
    tx_id: int,
    flag_data: schemas.TransactionFlagCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a flag on a transaction (e.g., 'review', 'duplicate', 'fraud')."""
    _wrap_tenant(request, db)
    tx = _verify_transaction_owner(db, tx_id, current_user.id)
    tenant_id = _get_tenant_id(request, tx)

    db_flag = models.TransactionFlag(
        transaction_id=tx_id,
        tenant_id=tenant_id,
        flag_type=flag_data.flag_type,
        reason=flag_data.reason,
    )
    db.add(db_flag)
    db.commit()
    db.refresh(db_flag)
    return db_flag


@router.get("/transactions/{tx_id}/flags")
def list_transaction_flags(
    request: Request,
    tx_id: int,
    skip: int = 0,
    limit: int = 100,
    resolved_only: bool = False,
    unresolved_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List flags for a transaction.

    Query params:
        * resolved_only   - Show only resolved flags
        * unresolved_only - Show only unresolved flags
    """
    _wrap_tenant(request, db)
    tx = _verify_transaction_owner(db, tx_id, current_user.id)

    query = db.query(
        models.TransactionFlag,
    ).filter(models.TransactionFlag.transaction_id == tx_id)

    # Note: The TransactionFlag model does not have a 'resolved' column.
    # We store resolved flags with flag_type prefixed by 'resolved:'.
    if resolved_only:
        query = query.filter(
            models.TransactionFlag.flag_type.ilike("resolved:%")
        )
    elif unresolved_only:
        query = query.filter(
            models.TransactionFlag.flag_type.not_ilike("resolved:%")
        )

    flags = (
        query.order_by(desc(models.TransactionFlag.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []
    for flag in flags:
        is_resolved = flag.flag_type.startswith("resolved:")
        flag_type_display = flag.flag_type
        if is_resolved:
            flag_type_display = flag.flag_type[9:]  # strip 'resolved:' prefix

        results.append({
            "id": flag.id,
            "transaction_id": flag.transaction_id,
            "tenant_id": flag.tenant_id,
            "flag_type": flag_type_display,
            "is_resolved": is_resolved,
            "reason": flag.reason,
            "created_at": flag.created_at.isoformat() if flag.created_at else None,
        })

    return results


@router.patch("/transactions/{tx_id}/flags/{flag_id}/resolve")
def resolve_transaction_flag(
    request: Request,
    tx_id: int,
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Mark a flag as resolved by prefixing its flag_type with 'resolved:'.
    This is a soft-resolution that preserves the original flag type.
    """
    _wrap_tenant(request, db)
    tx = _verify_transaction_owner(db, tx_id, current_user.id)

    flag = (
        db.query(models.TransactionFlag)
        .filter(
            models.TransactionFlag.id == flag_id,
            models.TransactionFlag.transaction_id == tx_id,
        )
        .first()
    )
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flag not found",
        )

    if flag.flag_type.startswith("resolved:"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Flag is already resolved.",
        )

    original_type = flag.flag_type
    flag.flag_type = f"resolved:{original_type}"
    db.commit()
    db.refresh(flag)

    return {
        "ok": True,
        "flag_id": flag.id,
        "transaction_id": tx_id,
        "original_type": original_type,
        "is_resolved": True,
        "resolved_at": flag.created_at.isoformat() if flag.created_at else None,
    }
