"""Vendor management API for TaxFlow Pro v3.11.6."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role

router = APIRouter(prefix="/vendors", tags=["vendors"])


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


class VendorCreate(BaseModel):
    name: str
    tax_id: Optional[str] = None
    address: Optional[str] = None
    is_1099_eligible: bool = False
    default_expense_coa_account_id: Optional[int] = None
    notes: Optional[str] = None


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    is_1099_eligible: Optional[bool] = None
    default_expense_coa_account_id: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("", response_model=dict, status_code=201)
def create_vendor(
    request: Request,
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Bookkeeper role required")
    vendor = models.Vendor(
        tenant_id=tenant_id,
        user_id=current_user.id,
        name=payload.name,
        tax_id=payload.tax_id,
        address=payload.address,
        is_1099_eligible=payload.is_1099_eligible,
        default_expense_coa_account_id=payload.default_expense_coa_account_id,
        notes=payload.notes,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return {
        "id": vendor.id,
        "name": vendor.name,
        "tax_id": vendor.tax_id,
        "address": vendor.address,
        "is_1099_eligible": vendor.is_1099_eligible,
        "default_expense_coa_account_id": vendor.default_expense_coa_account_id,
        "notes": vendor.notes,
        "is_active": vendor.is_active,
    }


@router.get("")
def list_vendors(
    request: Request,
    is_1099_eligible: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    q = db.query(models.Vendor).filter(models.Vendor.tenant_id == tenant_id)
    if is_1099_eligible is not None:
        q = q.filter(models.Vendor.is_1099_eligible == is_1099_eligible)
    vendors = q.order_by(models.Vendor.name).all()
    return [
        {
            "id": v.id,
            "name": v.name,
            "tax_id": v.tax_id,
            "address": v.address,
            "is_1099_eligible": v.is_1099_eligible,
            "default_expense_coa_account_id": v.default_expense_coa_account_id,
            "notes": v.notes,
            "is_active": v.is_active,
        }
        for v in vendors
    ]


@router.get("/{vendor_id}")
def get_vendor(
    request: Request,
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    vendor = db.query(models.Vendor).filter(
        models.Vendor.id == vendor_id,
        models.Vendor.tenant_id == tenant_id,
    ).first()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {
        "id": vendor.id,
        "name": vendor.name,
        "tax_id": vendor.tax_id,
        "address": vendor.address,
        "is_1099_eligible": vendor.is_1099_eligible,
        "default_expense_coa_account_id": vendor.default_expense_coa_account_id,
        "notes": vendor.notes,
        "is_active": vendor.is_active,
    }


@router.put("/{vendor_id}")
def update_vendor(
    request: Request,
    vendor_id: int,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Bookkeeper role required")
    vendor = db.query(models.Vendor).filter(
        models.Vendor.id == vendor_id,
        models.Vendor.tenant_id == tenant_id,
    ).first()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return {
        "id": vendor.id,
        "name": vendor.name,
        "tax_id": vendor.tax_id,
        "address": vendor.address,
        "is_1099_eligible": vendor.is_1099_eligible,
        "default_expense_coa_account_id": vendor.default_expense_coa_account_id,
        "notes": vendor.notes,
        "is_active": vendor.is_active,
    }
