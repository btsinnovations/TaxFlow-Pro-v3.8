"""Backup import/export router for TaxFlow Pro v3.11."""
from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..backup_import import BackupImportError, import_v3_10_backup
from ..database import get_db
from ..local import settings as local_settings
from ..rls import is_postgres, resolve_user_tenant_id
from .auth import get_current_user

router = APIRouter(prefix="/backup", tags=["backup"])


def _require_admin_or_single_user(current_user: models.User) -> None:
    """Restrict import to single-user local installs or admin roles."""
    if local_settings.is_single_user():
        return
    # Multi-entity mode requires explicit admin role.
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Backup import requires admin role")


def _wrap_tenant(request: Request, current_user: models.User) -> int:
    """Resolve tenant for the current request/user."""
    tenant_id = resolve_user_tenant_id(current_user)
    if is_postgres() and not local_settings.is_single_user():
        header = request.headers.get("x-tenant-id")
        if header is not None:
            try:
                tenant_id = int(header)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header") from exc
    return tenant_id


class BackupImportRequest(BaseModel):
    version: str = Field("3.10.0", description="Schema version of the backup being imported")
    users: list[Dict[str, Any]] = Field(default_factory=list)
    clients: list[Dict[str, Any]] = Field(default_factory=list)
    gl_accounts: list[Dict[str, Any]] = Field(default_factory=list)
    accounts: list[Dict[str, Any]] = Field(default_factory=list)
    statements: list[Dict[str, Any]] = Field(default_factory=list)
    transactions: list[Dict[str, Any]] = Field(default_factory=list)


class BackupImportResponse(BaseModel):
    ok: bool
    version: str
    counts: Dict[str, int]
    id_maps: Dict[str, Dict[int, int]]


class BackupExportResponse(BaseModel):
    version: str
    exported_at: str
    tenant_id: int
    users: list[Dict[str, Any]]
    clients: list[Dict[str, Any]]
    gl_accounts: list[Dict[str, Any]]
    accounts: list[Dict[str, Any]]
    statements: list[Dict[str, Any]]
    transactions: list[Dict[str, Any]]


@router.post("/import", response_model=BackupImportResponse)
def import_backup(
    request: Request,
    payload: BackupImportRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Import a v3.10 JSON backup into the current v3.11 database."""
    _require_admin_or_single_user(current_user)
    _wrap_tenant(request, current_user)

    data = payload.model_dump()
    try:
        result = import_v3_10_backup(db, data)
    except BackupImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Force JSON-serializable id_maps (int keys become strings automatically by FastAPI).
    return BackupImportResponse(
        ok=True,
        version=result["schema_version"],
        counts=result["counts"],
        id_maps=result["id_maps"],
    )


@router.get("/export", response_model=BackupExportResponse)
def export_backup(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Export the current tenant's data as a v3.11-compatible JSON backup."""
    tenant_id = _wrap_tenant(request, current_user)
    user_ids_query = (
        db.query(models.User.id)
        .join(models.Client, models.Client.user_id == models.User.id)
        .filter(models.Client.id == tenant_id)
    )
    user_ids = {row[0] for row in user_ids_query.all()}
    if current_user.id not in user_ids:
        user_ids.add(current_user.id)

    def _serialize_date(value):
        return value.isoformat() if value else None

    def _serialize_dt(value):
        return value.isoformat() if value else None

    users = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "hashed_password": u.hashed_password,
            "encryption_salt": u.encryption_salt,
            "keyfile_path": u.keyfile_path,
            "is_active": u.is_active,
            "created_at": _serialize_dt(u.created_at),
        }
        for u in db.query(models.User).filter(models.User.id.in_(user_ids)).all()
    ]

    clients = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "tax_id": c.tax_id,
            "user_id": c.user_id,
            "created_at": _serialize_dt(c.created_at),
        }
        for c in db.query(models.Client).filter(models.Client.id == tenant_id).all()
    ]

    gl_accounts = [
        {
            "id": g.id,
            "tenant_id": g.tenant_id,
            "user_id": g.user_id,
            "code": g.code,
            "name": g.name,
            "account_type": g.account_type,
            "is_active": g.is_active,
            "created_at": _serialize_dt(g.created_at),
        }
        for g in db.query(models.GLAccount).filter(models.GLAccount.tenant_id == tenant_id).all()
    ]

    accounts = [
        {
            "id": a.id,
            "name": a.name,
            "institution": a.institution,
            "account_number_masked": a.account_number_masked,
            "type": a.type,
            "client_id": a.client_id,
            "tenant_id": a.tenant_id,
            "user_id": a.user_id,
            "created_at": _serialize_dt(a.created_at),
        }
        for a in db.query(models.Account).filter(models.Account.tenant_id == tenant_id).all()
    ]

    statements = [
        {
            "id": s.id,
            "account_id": s.account_id,
            "tenant_id": s.tenant_id,
            "user_id": s.user_id,
            "filename": s.filename,
            "period_start": _serialize_date(s.period_start),
            "period_end": _serialize_date(s.period_end),
            "opening_balance": float(s.opening_balance) if s.opening_balance is not None else None,
            "closing_balance": float(s.closing_balance) if s.closing_balance is not None else None,
            "variance": float(s.variance) if s.variance is not None else None,
            "is_balanced": s.is_balanced,
            "created_at": _serialize_dt(s.created_at),
        }
        for s in db.query(models.Statement).filter(models.Statement.tenant_id == tenant_id).all()
    ]

    transactions = [
        {
            "id": t.id,
            "statement_id": t.statement_id,
            "tenant_id": t.tenant_id,
            "user_id": t.user_id,
            "gl_account_id": t.gl_account_id,
            "date": _serialize_date(t.date),
            "description": t.description,
            "amount": float(t.amount) if t.amount is not None else None,
            "tx_type": t.tx_type,
            "category": t.category,
            "running_balance": float(t.running_balance) if t.running_balance is not None else None,
            "workpaper_ref": t.workpaper_ref,
            "txn_uid": t.txn_uid,
            "fitid": t.fitid,
            "import_source": t.import_source,
            "created_at": _serialize_dt(t.created_at),
        }
        for t in db.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id).all()
    ]

    from datetime import datetime, timezone

    return BackupExportResponse(
        version="3.11.0",
        exported_at=datetime.now(timezone.utc).isoformat(),
        tenant_id=tenant_id,
        users=users,
        clients=clients,
        gl_accounts=gl_accounts,
        accounts=accounts,
        statements=statements,
        transactions=transactions,
    )
