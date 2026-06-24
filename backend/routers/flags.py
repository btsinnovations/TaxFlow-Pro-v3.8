"""Review flags router for TaxFlow Pro v3.9."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..services.flags import validate_flag_target
from ..audit import record, AuditAction, AuditResource
from .auth import get_current_user

router = APIRouter(prefix="/flags", tags=["flags"])


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


@router.get("/", response_model=List[schemas.FlagOut])
def list_flags(
    request: Request,
    tenant_id: int | None = None,
    resolved: bool | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    query = db.query(models.Flag).filter(
        models.Flag.tenant_id == effective_tenant_id,
        models.Flag.user_id == current_user.id,
    )
    if resolved is not None:
        query = query.filter(models.Flag.resolved == resolved)
    return query.order_by(models.Flag.created_at.desc()).all()


@router.post("/", response_model=schemas.FlagOut)
def create_flag(
    request: Request,
    payload: schemas.FlagCreate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    validate_flag_target(payload)

    if payload.transaction_id is not None:
        resource = db.query(models.Transaction).filter(
            models.Transaction.id == payload.transaction_id,
            models.Transaction.tenant_id == effective_tenant_id,
            models.Transaction.user_id == current_user.id,
        ).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Transaction not found")
    else:
        resource = db.query(models.GeneralLedgerEntry).filter(
            models.GeneralLedgerEntry.id == payload.journal_entry_id,
            models.GeneralLedgerEntry.tenant_id == effective_tenant_id,
            models.GeneralLedgerEntry.user_id == current_user.id,
        ).first()
        if not resource:
            raise HTTPException(status_code=404, detail="General ledger entry not found")

    flag = models.Flag(
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        transaction_id=payload.transaction_id,
        journal_entry_id=payload.journal_entry_id,
        note=payload.note,
        created_by=payload.created_by,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    record(db, current_user, AuditAction.CREATE, AuditResource.FLAG, flag.id,
           {"note": flag.note, "transaction_id": flag.transaction_id,
            "journal_entry_id": flag.journal_entry_id})
    return flag


@router.get("/{flag_id}", response_model=schemas.FlagOut)
def get_flag(
    request: Request,
    flag_id: int,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    flag = db.query(models.Flag).filter(
        models.Flag.id == flag_id,
        models.Flag.tenant_id == effective_tenant_id,
        models.Flag.user_id == current_user.id,
    ).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return flag


@router.put("/{flag_id}/resolve", response_model=schemas.FlagOut)
def resolve_flag(
    request: Request,
    flag_id: int,
    body: schemas.FlagResolve,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    flag = db.query(models.Flag).filter(
        models.Flag.id == flag_id,
        models.Flag.tenant_id == effective_tenant_id,
        models.Flag.user_id == current_user.id,
    ).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    flag.resolved = body.resolved
    flag.resolved_at = datetime.now(timezone.utc) if body.resolved else None
    db.commit()
    db.refresh(flag)
    record(db, current_user, AuditAction.UPDATE, AuditResource.FLAG, flag.id,
           {"resolved": flag.resolved})
    return flag


@router.delete("/{flag_id}")
def delete_flag(
    request: Request,
    flag_id: int,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    flag = db.query(models.Flag).filter(
        models.Flag.id == flag_id,
        models.Flag.tenant_id == effective_tenant_id,
        models.Flag.user_id == current_user.id,
    ).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    record(db, current_user, AuditAction.DELETE, AuditResource.FLAG, flag.id,
           {"note": flag.note})
    db.delete(flag)
    db.commit()
    return {"ok": True}
