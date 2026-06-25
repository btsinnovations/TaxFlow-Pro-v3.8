"""Tax filing export API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.tax_exports import schedule_c, set_mapping, list_mappings, SCHEDULE_C_LINES
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/tax-exports", tags=["tax-exports"])


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


class DateRange(BaseModel):
    start_date: date
    end_date: date


class Mapping(BaseModel):
    coa_account_id: int
    form: str
    line: str
    description: str | None = None


@router.post("/schedule-c")
def export_schedule_c(
    request: Request,
    payload: DateRange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    return schedule_c(db, tenant_id=tenant_id, user_id=current_user.id,
                      start_date=payload.start_date, end_date=payload.end_date)


@router.get("/lines")
def schedule_c_lines():
    return {"form": "Schedule C", "lines": SCHEDULE_C_LINES}


@router.post("/mappings", response_model=dict)
def create_mapping(
    request: Request,
    payload: Mapping,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    mapping = set_mapping(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        coa_account_id=payload.coa_account_id,
        form=payload.form,
        line=payload.line,
        description=payload.description,
    )
    return {"id": mapping.id, "form": mapping.form, "line": mapping.line}


@router.get("/mappings")
def get_mappings(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    rows = list_mappings(db, tenant_id=tenant_id, user_id=current_user.id)
    return [
        {
            "id": m.id,
            "coa_account_id": m.coa_account_id,
            "form": m.form,
            "line": m.line,
            "description": m.description,
        }
        for m in rows
    ]
