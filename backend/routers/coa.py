"""Chart of Accounts API endpoints for TaxFlow Pro v3.11.6."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.accounting.coa import (
    AccountType,
    create_account as create_coa_account,
    delete_account as delete_coa_account,
    get_accounts as get_coa_accounts,
    update_account as update_coa_account,
    seed_standard_coa as seed_coa,
    renumber_account as renumber_coa_account,
    reassign_parent as reassign_coa_parent,
)
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.schemas import COAAccountCreate, COAAccountTree, COAAccountUpdate
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role
from backend import models

router = APIRouter(tags=["coa"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User) -> int:
    """Resolve tenant_id for the request and apply Postgres RLS if needed."""
    if not is_postgres():
        # SQLite dev/tests: infer tenant from the user's primary client.
        return resolve_user_tenant_id(current_user)
    if local_settings.is_single_user():
        tenant_id = resolve_user_tenant_id(current_user)
        set_tenant_id(db, tenant_id)
        return tenant_id
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    try:
        tenant_id_int = int(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header")
    set_tenant_id(db, tenant_id_int)
    return tenant_id_int


@router.get("/coa", response_model=list[COAAccountTree])
def list_coa(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return the chart of accounts for the current tenant."""
    tenant_id = _wrap_tenant(request, db, current_user)
    return get_coa_accounts(db, tenant_id=tenant_id, user_id=current_user.id)


@router.post("/coa", response_model=COAAccountTree, status_code=201)
def create_account(
    request: Request,
    payload: COAAccountCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a new chart of accounts entry.

    Requires bookkeeper role or higher on the active profile/tenant.
    """
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Insufficient profile role (bookkeeper required)")
    return create_coa_account(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        code=payload.number,
        name=payload.name,
        account_type=payload.type.value,
        parent_id=payload.parent_id,
        is_active=payload.is_active,
    )


@router.put("/coa/{account_id}", response_model=COAAccountTree)
def update_account(
    request: Request,
    account_id: int,
    payload: COAAccountUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update an existing chart of accounts entry.

    Requires bookkeeper role or higher on the active profile/tenant.
    """
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Insufficient profile role (bookkeeper required)")
    data = payload.model_dump(exclude_unset=True)
    type_value = data.get("type")
    account_type = None
    if isinstance(type_value, str):
        account_type = type_value
    elif isinstance(type_value, AccountType):
        account_type = type_value.value
    elif isinstance(type_value, dict) and "value" in type_value:
        account_type = type_value["value"]
    return update_coa_account(
        db=db,
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        code=data.get("number"),
        name=data.get("name"),
        account_type=account_type,
        parent_id=data.get("parent_id"),
        is_active=data.get("is_active"),
    )


@router.delete("/coa/{account_id}")
def delete_account(
    request: Request,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a COA account if it is not referenced elsewhere.

    Requires admin role or higher on the active profile/tenant.
    """
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.admin):
        raise HTTPException(status_code=403, detail="Insufficient profile role (admin required)")
    delete_coa_account(
        db=db,
        account_id=account_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
    )
    return {"ok": True}


@router.post("/coa/seed", response_model=list[COAAccountTree])
def seed_standard_coa(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Seed a standard small-business COA for the current tenant.

    Requires admin role or higher on the active profile/tenant.
    """
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.admin):
        raise HTTPException(status_code=403, detail="Insufficient profile role (admin required)")
    return seed_coa(db=db, tenant_id=tenant_id, user_id=current_user.id)


@router.patch("/coa/{account_id}/renumber", response_model=COAAccountTree)
def renumber_account(
    request: Request,
    account_id: int,
    new_number: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Renumber an existing COA account.

    Requires admin role or higher on the active profile/tenant.
    """
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.admin):
        raise HTTPException(status_code=403, detail="Insufficient profile role (admin required)")
    return renumber_coa_account(
        db=db,
        account_id=account_id,
        tenant_id=tenant_id,
        new_number=new_number,
    )


@router.patch("/coa/{account_id}/parent", response_model=COAAccountTree)
def reassign_parent(
    request: Request,
    account_id: int,
    new_parent_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Reassign the parent of a COA account.

    Requires admin role or higher on the active profile/tenant.
    """
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.admin):
        raise HTTPException(status_code=403, detail="Insufficient profile role (admin required)")
    return reassign_coa_parent(
        db=db,
        account_id=account_id,
        tenant_id=tenant_id,
        new_parent_id=new_parent_id,
    )