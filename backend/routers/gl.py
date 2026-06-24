"""GL account and general ledger entry router for TaxFlow Pro v3.9."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..audit import record, AuditAction, AuditResource
from .auth import get_current_user

router = APIRouter(prefix="/ledger", tags=["ledger"])


def _resolve_tenant_id(request: Request, current_user: models.User) -> int:
    if local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return int(tenant_id)


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    set_tenant_id(db, _resolve_tenant_id(request, current_user))


@router.post("/accounts", response_model=schemas.GLAccount)
def create_gl_account(
    request: Request,
    account: schemas.GLAccountCreate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
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
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
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
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    db_entry = models.GeneralLedgerEntry(
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        date=entry.date,
        description=entry.description,
        debit_account_id=entry.debit_account_id,
        credit_account_id=entry.credit_account_id,
        amount=entry.amount,
        memo=entry.memo,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    record(db, current_user, AuditAction.CREATE, AuditResource.GENERAL_LEDGER_ENTRY, db_entry.id,
           {"debit_account_id": db_entry.debit_account_id, "credit_account_id": db_entry.credit_account_id,
            "amount": str(db_entry.amount)})
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
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
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
