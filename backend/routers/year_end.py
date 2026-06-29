"""Year-end closing API endpoint for TaxFlow Pro v3.11.6."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role
from backend.accounting.year_end import close_year

router = APIRouter(prefix="/year-end", tags=["year-end"])


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


class CloseYearRequest(BaseModel):
    year: int


@router.post("/close", response_model=dict)
def close_year_endpoint(
    request: Request,
    payload: CloseYearRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.admin):
        raise HTTPException(status_code=403, detail="Admin role required")
    result = close_year(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        year=payload.year,
    )
    return result
