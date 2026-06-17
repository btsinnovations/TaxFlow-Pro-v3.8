"""Audit log endpoints."""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..audit.audit_trail import (
    ACTION_ARCHIVE_YEAR,
    ACTION_CREATE_JOURNAL,
    ACTION_CREATE_STATEMENT,
    ACTION_CREATE_TRANSACTION,
    ACTION_DELETE_JOURNAL,
    ACTION_DELETE_TRANSACTION,
    ACTION_LOCK_PERIOD,
    ACTION_POST_JOURNAL,
    ACTION_RESTORE_YEAR,
    ACTION_SIGN_REPORT,
    ACTION_UNLOCK_PERIOD,
    ACTION_UPDATE_JOURNAL,
    ACTION_UPDATE_TRANSACTION,
    ACTION_UPLOAD_RECEIPT,
)
from ..database import get_db
from ..rls import is_postgres, set_tenant_id
from .auth import get_current_user

router = APIRouter(prefix="/audit", tags=["audit"])

# Map audit actions to frontend-facing event types and severities.
_ACTION_EVENT_MAP: Dict[str, Tuple[str, str]] = {
    ACTION_CREATE_TRANSACTION: ("PROCESS", "INFO"),
    ACTION_UPDATE_TRANSACTION: ("PROCESS", "INFO"),
    ACTION_DELETE_TRANSACTION: ("PROCESS", "WARNING"),
    ACTION_CREATE_STATEMENT: ("FILE_UPLOAD", "INFO"),
    ACTION_CREATE_JOURNAL: ("USER_ACTION", "INFO"),
    ACTION_UPDATE_JOURNAL: ("USER_ACTION", "INFO"),
    ACTION_DELETE_JOURNAL: ("USER_ACTION", "WARNING"),
    ACTION_POST_JOURNAL: ("USER_ACTION", "INFO"),
    ACTION_LOCK_PERIOD: ("USER_ACTION", "WARNING"),
    ACTION_UNLOCK_PERIOD: ("USER_ACTION", "INFO"),
    ACTION_SIGN_REPORT: ("USER_ACTION", "INFO"),
    ACTION_UPLOAD_RECEIPT: ("FILE_UPLOAD", "INFO"),
    ACTION_ARCHIVE_YEAR: ("SYSTEM", "INFO"),
    ACTION_RESTORE_YEAR: ("SYSTEM", "INFO"),
}


def _normalize_audit_entry(entry: models.AuditEntry, username: str) -> Dict[str, Any]:
    event_type, severity = _ACTION_EVENT_MAP.get(entry.action, ("SYSTEM", "INFO"))
    details: Dict[str, Any] = {}
    if entry.details:
        try:
            import json

            details = json.loads(entry.details)
        except Exception:
            pass

    description = details.get("description") or f"{entry.action}: {entry.entity_type} #{entry.entity_id}"
    return {
        "id": entry.id,
        "timestamp": entry.created_at.isoformat() if entry.created_at else None,
        "severity": severity,
        "event_type": event_type,
        "client_id": entry.tenant_id,
        "description": description,
        "user": username,
        "session_id": "—",
        "details": details,
    }


def _normalize_statement(statement: models.Statement, username: str) -> Dict[str, Any]:
    institution = None
    if statement.account:
        institution = statement.account.institution

    transaction_count = len(statement.transactions) if statement.transactions else 0

    return {
        "id": f"stmt-{statement.id}",
        "timestamp": statement.created_at.isoformat() if statement.created_at else None,
        "severity": "INFO",
        "event_type": "FILE_UPLOAD",
        "client_id": statement.tenant_id,
        "description": f"Uploaded {statement.filename or 'statement'} ({transaction_count} transactions)",
        "user": username,
        "session_id": "—",
        "details": {
            "file_id": statement.id,
            "filename": statement.filename,
            "institution": institution,
            "transaction_count": transaction_count,
            "account_id": statement.account_id,
            "is_balanced": statement.is_balanced,
            "variance": float(statement.variance) if statement.variance is not None else None,
        },
    }


def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


@router.get("/logs")
def get_logs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return a unified audit log for the current user."""
    _wrap_tenant(request, db)

    # Collect audit entries authored by this user.
    audit_entries = (
        db.query(models.AuditEntry)
        .filter(models.AuditEntry.user_id == current_user.id)
        .order_by(models.AuditEntry.created_at.desc())
        .all()
    )

    # Collect statement uploads authored by this user.
    statements = (
        db.query(models.Statement)
        .options(joinedload(models.Statement.account))
        .filter(models.Statement.user_id == current_user.id)
        .order_by(models.Statement.created_at.desc())
        .all()
    )

    events: List[Dict[str, Any]] = []
    events.extend(_normalize_audit_entry(e, current_user.username) for e in audit_entries)
    events.extend(_normalize_statement(s, current_user.username) for s in statements)

    # Sort newest first, paginate.
    events.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return events[skip : skip + limit]
