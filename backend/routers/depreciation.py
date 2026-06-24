"""Depreciation asset router for TaxFlow Pro v3.9."""
from __future__ import annotations
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..services.depreciation import compute_schedule
from ..audit import record, AuditAction, AuditResource
from .auth import get_current_user

router = APIRouter(prefix="/depreciation", tags=["depreciation"])


def _resolve_tenant_id(request: Request, current_user: models.User) -> int:
    if local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return int(tenant_id)


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    set_tenant_id(db, _resolve_tenant_id(request, current_user))


def _asset_schedule(asset: models.DepreciationAsset) -> List[schemas.DepreciationScheduleEntryOut]:
    schedule = compute_schedule(
        cost_basis=asset.cost_basis,
        placed_in_service_date=asset.placed_in_service_date,
        recovery_period_years=asset.recovery_period_years,
        method=asset.method,
        convention=asset.convention,
        section_179=asset.section_179,
        bonus_depreciation=asset.bonus_depreciation,
        salvage_value=asset.salvage_value,
    )
    return [
        schemas.DepreciationScheduleEntryOut(
            year=entry.year,
            beginning_basis=float(entry.beginning_basis),
            section_179=float(entry.section_179),
            bonus=float(entry.bonus),
            regular_depreciation=float(entry.regular_depreciation),
            ending_basis=float(entry.ending_basis),
        )
        for entry in schedule
    ]


@router.get("/", response_model=List[schemas.DepreciationAsset])
def list_assets(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    return (
        db.query(models.DepreciationAsset)
        .filter(models.DepreciationAsset.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/", response_model=schemas.DepreciationAssetWithSchedule)
def create_asset(
    request: Request,
    asset: schemas.DepreciationAssetCreate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    db_asset = models.DepreciationAsset(
        **asset.model_dump(),
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
    )
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    record(db, current_user, AuditAction.CREATE, AuditResource.ASSET, db_asset.id, {"name": db_asset.name})
    out = schemas.DepreciationAssetWithSchedule.model_validate(db_asset)
    out.schedule = _asset_schedule(db_asset)
    return out


@router.get("/{asset_id}", response_model=schemas.DepreciationAssetWithSchedule)
def get_asset(
    request: Request,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    db_asset = (
        db.query(models.DepreciationAsset)
        .filter(models.DepreciationAsset.id == asset_id, models.DepreciationAsset.user_id == current_user.id)
        .first()
    )
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    out = schemas.DepreciationAssetWithSchedule.model_validate(db_asset)
    out.schedule = _asset_schedule(db_asset)
    return out


@router.patch("/{asset_id}", response_model=schemas.DepreciationAssetWithSchedule)
def update_asset(
    request: Request,
    asset_id: int,
    asset_update: schemas.DepreciationAssetUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    db_asset = (
        db.query(models.DepreciationAsset)
        .filter(models.DepreciationAsset.id == asset_id, models.DepreciationAsset.user_id == current_user.id)
        .first()
    )
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    changes = asset_update.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(db_asset, key, value)
    db.commit()
    db.refresh(db_asset)
    record(db, current_user, AuditAction.UPDATE, AuditResource.ASSET, db_asset.id, changes)
    out = schemas.DepreciationAssetWithSchedule.model_validate(db_asset)
    out.schedule = _asset_schedule(db_asset)
    return out


@router.delete("/{asset_id}")
def delete_asset(
    request: Request,
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    db_asset = (
        db.query(models.DepreciationAsset)
        .filter(models.DepreciationAsset.id == asset_id, models.DepreciationAsset.user_id == current_user.id)
        .first()
    )
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    record(db, current_user, AuditAction.DELETE, AuditResource.ASSET, db_asset.id, {"name": db_asset.name})
    db.delete(db_asset)
    db.commit()
    return {"ok": True}
