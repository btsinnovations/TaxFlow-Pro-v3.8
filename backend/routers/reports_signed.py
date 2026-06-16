"""
Signed Report router for TaxFlow Pro v3.8.

Provides cryptographically signed report generation using HMAC-SHA256.
Reports are tamper-evident: the signature hash covers the canonical
JSON representation of the report data and is stored alongside the
signed report record.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id
from ..audit.audit_trail import create_audit_entry, ACTION_SIGN_REPORT
from .auth import get_current_user

router = APIRouter(prefix="/reports", tags=["reports-signed"])

# Load signing secret from environment; falls back to a dev-only default.
_SIGN_SECRET = os.environ.get(
    "TAXFLOW_SIGN_SECRET",
    "taxflow-sign-secret-dev-only-change-in-production-2026"
).encode("utf-8")


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


def _compute_signature(report_data: dict, user_id: int, timestamp: str) -> str:
    """
    Compute HMAC-SHA256 signature over canonical JSON of report data.

    The payload includes the report data, user_id, and timestamp to
    prevent replay and ensure non-repudiation.
    """
    payload = {
        "report_data": report_data,
        "user_id": user_id,
        "timestamp": timestamp,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(_SIGN_SECRET, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------

class SignReportRequest(BaseModel):
    client_id: int
    year: Optional[str] = None
    title: str
    report_data: dict
    master_password: str


class SignedReportMetadata(schemas.SignedReport):
    """Signed report schema that excludes the report_data field for list views."""
    pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{report_type}/sign", response_model=schemas.SignedReport)
def sign_report(
    request: Request,
    report_type: str,
    sign_req: SignReportRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Sign a report with HMAC-SHA256.

    Requires *master_password* to match the current user's password hash.
    The signature covers the canonical JSON of *report_data*, *user_id*,
    and the signing timestamp.
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, sign_req.client_id)

    # Verify master password
    from .auth import verify_password
    if not verify_password(sign_req.master_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid master password.",
        )

    # Validate report type
    valid_types = {"pl", "balance_sheet", "cash_flow", "tax_summary", "general_ledger", "trial_balance"}
    if report_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type. Must be one of: {', '.join(sorted(valid_types))}",
        )

    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()

    # Compute HMAC signature
    signature_hash = _compute_signature(sign_req.report_data, current_user.id, timestamp)

    # Determine period boundaries from year if provided
    period_start = None
    period_end = None
    if sign_req.year:
        period_start = f"{sign_req.year}-01-01"
        period_end = f"{sign_req.year}-12-31"

    # Persist the signed report
    db_report = models.SignedReport(
        tenant_id=tenant_id,
        user_id=current_user.id,
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        file_path=sign_req.title,
        signature_hash=signature_hash,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    # Audit trail
    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_SIGN_REPORT,
        entity_type="SignedReport",
        entity_id=db_report.id,
        new_values={
            "report_type": report_type,
            "title": sign_req.title,
            "year": sign_req.year,
            "signature_hash_prefix": signature_hash[:16],
        },
        client_id=tenant_id,
    )
    db.commit()

    return db_report


@router.get("/signed", response_model=List[schemas.SignedReport])
def list_signed_reports(
    request: Request,
    client_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List signed reports for a client. Returns metadata only
    (the ``report_data`` is not stored in the database; it is
    provided at signing time and the signature covers it).
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    return (
        db.query(models.SignedReport)
        .filter(
            models.SignedReport.tenant_id == tenant_id,
            models.SignedReport.user_id == current_user.id,
        )
        .order_by(models.SignedReport.signed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/signed/{report_id}", response_model=schemas.SignedReport)
def get_signed_report(
    request: Request,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get a single signed report including full metadata and signature hash."""
    _wrap_tenant(request, db)
    report = (
        db.query(models.SignedReport)
        .filter(
            models.SignedReport.id == report_id,
            models.SignedReport.user_id == current_user.id,
        )
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signed report not found",
        )
    return report
