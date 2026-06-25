"""Audit trail router for TaxFlow Pro v3.9."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..audit import verify_chain, AuditAction, AuditResource
from ..utils.redaction import mask_account_number, redact_description
from .auth import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id:
        set_tenant_id(db, int(tenant_id))
        return
    set_tenant_id(db, resolve_user_tenant_id(current_user))


@router.get("/")
def get_audit_root(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Minimal audit log listing for the v3.10 packaged UI."""
    _wrap_tenant(request, db, current_user)
    entries = db.query(models.AuditEntry).filter(
        models.AuditEntry.actor_id == current_user.id
    ).order_by(models.AuditEntry.id.desc()).offset(skip).limit(limit).all()
    return _redact_audit_entries([
        {
            "id": e.id,
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "severity": e.details_dict().get("severity", "INFO"),
            "event_type": e.action,
            "client_id": e.resource_id,
            "description": e.description,
            "user": current_user.username,
            "session_id": e.session_id,
            "details": e.details_dict(),
        }
        for e in entries
    ])


@router.get("/logs", response_model=List[schemas.AuditEntryOut])
def get_logs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    resource_type: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    query = db.query(models.AuditEntry).filter(
        models.AuditEntry.actor_id == current_user.id
    ).order_by(models.AuditEntry.id.desc())
    if resource_type:
        query = query.filter(models.AuditEntry.resource_type == resource_type)
    entries = query.offset(skip).limit(limit).all()
    out = []
    for e in entries:
        dto = schemas.AuditEntryOut.model_validate(e)
        dto.details = e.details_dict()
        out.append(dto)
    return _redact_audit_entries(out)


@router.get("/verify")
def verify_audit_chain(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    valid, first_bad_id = verify_chain(db)
    count = db.query(models.AuditEntry).count()
    return {
        "valid": valid,
        "first_bad_id": int(first_bad_id) if first_bad_id is not None else None,
        "count": count,
    }
