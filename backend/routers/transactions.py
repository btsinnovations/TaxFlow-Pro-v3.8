"""Transaction router for TaxFlow Pro v3.9."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..audit import record, AuditAction, AuditResource
from ..local.column_encryption import decrypt_for_user
from .auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    if local_settings.is_single_user():
        set_tenant_id(db, resolve_user_tenant_id(current_user))
        return
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    set_tenant_id(db, int(tenant_id))


@router.put("/{transaction_id}/workpaper-ref", response_model=schemas.Transaction)
def update_workpaper_ref(
    request: Request,
    transaction_id: int,
    tenant_id: int,
    update: schemas.WorkpaperRefUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    tx = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == current_user.id,
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx.workpaper_ref = update.workpaper_ref
    db.commit()
    db.refresh(tx)
    record(db, current_user, AuditAction.UPDATE, AuditResource.TRANSACTION, tx.id,
           {"workpaper_ref": tx.workpaper_ref})
    return {
        "id": tx.id,
        "date": tx.date,
        "description": decrypt_for_user(tx.description, current_user),
        "amount": float(tx.amount) if tx.amount is not None else None,
        "tx_type": tx.tx_type,
        "category": tx.category,
        "running_balance": float(tx.running_balance) if tx.running_balance is not None else None,
        "workpaper_ref": tx.workpaper_ref,
        "statement_id": tx.statement_id,
        "tenant_id": tx.tenant_id,
        "gl_account_id": tx.gl_account_id,
        "created_at": tx.created_at,
    }
