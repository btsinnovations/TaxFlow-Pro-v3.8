"""Import router for TaxFlow Pro v3.11.

Exposes parser detection and (soon) OFX import endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from .. import models, schemas
from ..parsers.institution import detect_institution_with_columns
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
