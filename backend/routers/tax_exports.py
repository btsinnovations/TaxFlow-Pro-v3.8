"""Tax filing export API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.local.roles import Role, has_role
from backend.accounting.tax_exports import (
    schedule_c,
    schedule_c_csv,
    set_mapping,
    delete_mapping,
    list_mappings,
    SCHEDULE_C_LINES,
    form_1099_nec_misc,
    year_end_summary,
)
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


def _require_role(db: Session, current_user: models.User, tenant_id: int, min_role: Role):
    if not has_role(db, current_user.id, tenant_id, min_role):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient profile role ({min_role.name} required)",
        )


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
    format: str = "json",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    result = schedule_c(db, tenant_id=tenant_id, user_id=current_user.id,
                        start_date=payload.start_date, end_date=payload.end_date)
    if format.lower() == "csv":
        csv_data = schedule_c_csv(result)
        return {"format": "csv", "content": csv_data}
    return result


@router.get("/lines")
def schedule_c_lines(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, _wrap_tenant(request, db, current_user), Role.viewer)
    return {"form": "Schedule C", "lines": SCHEDULE_C_LINES}


@router.post("/1099")
def export_1099(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    year: int = date.today().year - 1,
    threshold: float = 600.0,
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    return form_1099_nec_misc(
        db, tenant_id=tenant_id, user_id=current_user.id,
        year=year, threshold=Decimal(str(threshold)),
    )


@router.post("/year-end-summary")
def export_year_end_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    year: int = date.today().year - 1,
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    return year_end_summary(db, tenant_id=tenant_id, user_id=current_user.id, year=year)


@router.post("/mappings", response_model=dict)
def create_mapping(
    request: Request,
    payload: Mapping,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
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


@router.delete("/mappings/{mapping_id}", response_model=dict)
def remove_mapping(
    request: Request,
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.admin)
    ok = delete_mapping(db, tenant_id=tenant_id, user_id=current_user.id, mapping_id=mapping_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"ok": True}


@router.get("/mappings")
def get_mappings(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
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
