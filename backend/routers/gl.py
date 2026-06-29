"""GL account and general ledger entry router for TaxFlow Pro v3.9."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from .. import models, schemas
from ..database import get_db
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..local.roles import Role, has_role
from ..audit import record, AuditAction, AuditResource
from .auth import get_current_user

router = APIRouter(prefix="/ledger", tags=["ledger"])


class AdjustingEntryRequest(schemas.GeneralLedgerEntryCreate):
    review_flag_id: Optional[int] = None


def _resolve_tenant_id(request: Request, current_user: models.User, db: Session | None = None) -> int:
    header_tid = request.headers.get("x-tenant-id")
    if header_tid is not None and db is not None:
        from ..local.roles import has_role
        try:
            tid = int(header_tid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header")
        if has_role(db, current_user.id, tid, "viewer"):
            return tid
    if local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)
    if header_tid is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return int(header_tid)


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    set_tenant_id(db, _resolve_tenant_id(request, current_user, db=db))


@router.post("/accounts", response_model=schemas.GLAccount)
def create_gl_account(
    request: Request,
    account: schemas.GLAccountCreate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user, db=db) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    db_account = models.GLAccount(
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        code=account.code,
        name=account.name,
        account_type=account.account_type,
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


@router.get("/accounts", response_model=List[schemas.GLAccount])
def list_gl_accounts(
    request: Request,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user, db=db) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    return db.query(models.GLAccount).filter(
        models.GLAccount.tenant_id == effective_tenant_id,
        models.GLAccount.user_id == current_user.id,
    ).order_by(models.GLAccount.code.asc()).all()


@router.post("/entries", response_model=schemas.GeneralLedgerEntryOut)
def create_gl_entry(
    request: Request,
    entry: schemas.GeneralLedgerEntryCreate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user, db=db) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    db_entry = models.GeneralLedgerEntry(
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        date=entry.date,
        description=entry.description,
        debit_account_id=entry.debit_account_id,
        credit_account_id=entry.credit_account_id,
        debit_coa_account_id=entry.debit_coa_account_id,
        credit_coa_account_id=entry.credit_coa_account_id,
        amount=entry.amount,
        memo=entry.memo,
        entry_type=entry.entry_type or "regular",
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    record(db, current_user, AuditAction.CREATE, AuditResource.GENERAL_LEDGER_ENTRY, db_entry.id,
           {"debit_account_id": db_entry.debit_account_id, "credit_account_id": db_entry.credit_account_id,
            "debit_coa_account_id": db_entry.debit_coa_account_id, "credit_coa_account_id": db_entry.credit_coa_account_id,
            "entry_type": db_entry.entry_type, "amount": str(db_entry.amount)})
    return db_entry


@router.post("/adjusting-entry", response_model=schemas.GeneralLedgerEntryOut)
def create_adjusting_entry(
    request: Request,
    payload: AdjustingEntryRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a manual adjusting journal entry.

    Same payload as /ledger/entries plus optional review_flag_id. Requires
    bookkeeper role minimum. Sets entry_type='adjusting'.
    """
    effective_tenant_id = _resolve_tenant_id(request, current_user, db=db)
    _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, effective_tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Bookkeeper role required")

    db_entry = models.GeneralLedgerEntry(
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        date=payload.date,
        description=payload.description,
        debit_account_id=payload.debit_account_id,
        credit_account_id=payload.credit_account_id,
        debit_coa_account_id=payload.debit_coa_account_id,
        credit_coa_account_id=payload.credit_coa_account_id,
        amount=payload.amount,
        memo=payload.memo,
        entry_type="adjusting",
    )
    db.add(db_entry)
    db.flush()

    if payload.review_flag_id is not None:
        flag = db.query(models.Flag).filter(
            models.Flag.id == payload.review_flag_id,
            models.Flag.tenant_id == effective_tenant_id,
        ).first()
        if flag is not None:
            flag.journal_entry_id = db_entry.id
            flag.resolved = True
            flag.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(db_entry)
    record(db, current_user, AuditAction.CREATE, AuditResource.GENERAL_LEDGER_ENTRY, db_entry.id,
           {"entry_type": db_entry.entry_type, "amount": str(db_entry.amount)})
    return db_entry


@router.put("/entries/{entry_id}/workpaper-ref", response_model=schemas.GeneralLedgerEntryOut)
def update_gl_workpaper_ref(
    request: Request,
    entry_id: int,
    update: schemas.WorkpaperRefUpdate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user, db=db) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    entry = db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.id == entry_id,
        models.GeneralLedgerEntry.tenant_id == effective_tenant_id,
        models.GeneralLedgerEntry.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="General ledger entry not found")
    entry.workpaper_ref = update.workpaper_ref
    db.commit()
    db.refresh(entry)
    record(db, current_user, AuditAction.UPDATE, AuditResource.GENERAL_LEDGER_ENTRY, entry.id,
           {"workpaper_ref": entry.workpaper_ref})
    return entry


# R1: Auto-post batch endpoint
@router.post("/auto-post-batch")
def auto_post_batch(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Post GL entries for all transactions that don't have them yet."""
    from backend.accounting.gl_bridge import GLBridge
    from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
    from backend.local import settings as local_settings
    from backend.local.roles import Role, has_role

    if not is_postgres():
        tenant_id = resolve_user_tenant_id(current_user)
    else:
        if local_settings.is_single_user():
            tenant_id = resolve_user_tenant_id(current_user)
            set_tenant_id(db, tenant_id)
        else:
            tid = request.headers.get("x-tenant-id")
            if tid is None:
                raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
            tenant_id = int(tid)

    if not has_role(db, current_user.id, tenant_id, Role.admin):
        raise HTTPException(status_code=403, detail="Admin role required")

    txns = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == current_user.id,
    ).all()

    bridge = GLBridge(db, tenant_id=tenant_id, user_id=current_user.id)
    posted = 0
    for txn in txns:
        if not bridge.is_already_posted(txn):
            entries = bridge.post_for_transaction(txn)
            posted += len(entries)
    db.commit()
    return {"posted_entries": posted, "total_txns": len(txns)}
