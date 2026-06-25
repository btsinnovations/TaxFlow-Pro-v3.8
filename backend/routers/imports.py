"""Import router for TaxFlow Pro v3.11.

Exposes parser detection and (soon) OFX import endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from .. import models, schemas
from ..parsers.institution import detect_institution_with_columns
from ..parsers.ofx import OFXParseError, parse_ofx
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from .auth import get_current_user

router = APIRouter(prefix="/imports", tags=["imports"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User) -> int:
    if not is_postgres():
        return resolve_user_tenant_id(current_user)
    if local_settings.is_single_user():
        tenant_id = resolve_user_tenant_id(current_user)
        set_tenant_id(db, tenant_id)
        return tenant_id
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    try:
        return int(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header")


class ImportDetectRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw statement text / PDF text sample")
    rows: Optional[List[List[str]]] = Field(default=None, description="Optional CSV row sample")


class ImportDetectResponse(BaseModel):
    institution: str
    confidence: float
    layout: str
    expected_columns: List[str]
    notes: dict


@router.post("/detect", response_model=ImportDetectResponse)
def detect_import(
    request: Request,
    payload: ImportDetectRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Detect the financial institution from sample statement text/rows."""
    # Tenant resolution for audit/logging consistency; detection itself is stateless.
    _wrap_tenant(request, db, current_user)

    sample = payload.text
    if payload.rows:
        # Flatten CSV rows into the text for column-aware detection.
        sample += "\n" + "\n".join(" ".join(row) for row in payload.rows)

    result = detect_institution_with_columns(sample)
    return ImportDetectResponse(
        institution=result["institution"],
        confidence=result["confidence"],
        layout=result["layout"],
        expected_columns=result["expected_columns"],
        notes=result.get("notes", {}),
    )


class OFXImportResponse(BaseModel):
    statement_id: int
    account_id: int
    account_name: str
    transactions_count: int
    duplicates_skipped: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None


@router.post("/ofx", response_model=OFXImportResponse)
async def import_ofx(
    request: Request,
    file: UploadFile = File(...),
    account_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Import an OFX/QFX statement, mapping/creating an account and writing transactions."""
    tenant_id = _wrap_tenant(request, db, current_user)

    if not file.filename.lower().endswith((".ofx", ".qfx")):
        raise HTTPException(status_code=415, detail="Only .ofx and .qfx files are supported")

    try:
        content = await file.read()
        parsed = parse_ofx(content)
    except OFXParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse OFX file: {exc}") from exc

    account = None
    if account_id is not None:
        account = db.query(models.Account).filter(
            models.Account.id == account_id,
            models.Account.user_id == current_user.id,
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
    else:
        # Map by account number (exact match on masked or full account_id field).
        account = db.query(models.Account).filter(
            models.Account.user_id == current_user.id,
            models.Account.tenant_id == tenant_id,
            or_(
                models.Account.account_number_masked == parsed.account.account_id,
                models.Account.name == parsed.account.account_id,
            ),
        ).first()
        if not account:
            account = models.Account(
                user_id=current_user.id,
                tenant_id=tenant_id,
                client_id=tenant_id,
                name=parsed.account.account_id or f"Imported {parsed.account.account_type}",
                institution="OFX Import",
                account_number_masked=parsed.account.account_id,
                type=parsed.account.account_type,
            )
            db.add(account)
            db.commit()
            db.refresh(account)

    statement = models.Statement(
        account_id=account.id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        filename=file.filename,
        period_start=parsed.period_start,
        period_end=parsed.period_end,
        opening_balance=parsed.opening_balance,
        closing_balance=parsed.closing_balance,
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)

    duplicates_skipped = 0
    created_count = 0
    for tx in parsed.transactions:
        # Deduplicate by FITID within the same account/tenant/user.
        existing = db.query(models.Transaction).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == current_user.id,
            models.Transaction.fitid == tx.fitid,
        ).first()
        if existing is not None:
            duplicates_skipped += 1
            continue

        db_tx = models.Transaction(
            statement_id=statement.id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            date=tx.date,
            description=tx.description,
            amount=tx.amount,
            tx_type="credit" if tx.amount > 0 else "debit",
            fitid=tx.fitid,
            import_source="ofx",
        )
        db.add(db_tx)
        created_count += 1

    db.commit()

    return OFXImportResponse(
        statement_id=statement.id,
        account_id=account.id,
        account_name=account.name,
        transactions_count=created_count,
        duplicates_skipped=duplicates_skipped,
        period_start=str(parsed.period_start) if parsed.period_start else None,
        period_end=str(parsed.period_end) if parsed.period_end else None,
    )

