"""Mileage log API for TaxFlow Pro v3.11.6."""
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

router = APIRouter(prefix="/mileage", tags=["mileage"])


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


class MileageLogCreate(BaseModel):
    trip_date: date
    description: str
    starting_odometer: float
    ending_odometer: float
    purpose: Optional[str] = "business"
    vehicle: Optional[str] = None
    reimbursement_rate: Optional[float] = None


@router.post("/logs", response_model=dict, status_code=201)
def create_log(
    request: Request,
    payload: MileageLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Bookkeeper role required")
    miles = Decimal(str(payload.ending_odometer)) - Decimal(str(payload.starting_odometer))
    rate = Decimal(str(payload.reimbursement_rate)) if payload.reimbursement_rate is not None else Decimal("0.00")
    reimbursement = miles * rate
    log = models.MileageLog(
        tenant_id=tenant_id,
        user_id=current_user.id,
        trip_date=payload.trip_date,
        description=payload.description,
        starting_odometer=Decimal(str(payload.starting_odometer)),
        ending_odometer=Decimal(str(payload.ending_odometer)),
        miles=miles,
        purpose=payload.purpose or "business",
        vehicle=payload.vehicle,
        reimbursement_rate=rate,
        reimbursement_amount=reimbursement,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "id": log.id,
        "trip_date": log.trip_date.isoformat(),
        "description": log.description,
        "starting_odometer": float(log.starting_odometer),
        "ending_odometer": float(log.ending_odometer),
        "miles": float(log.miles),
        "purpose": log.purpose,
        "vehicle": log.vehicle,
        "reimbursement_rate": float(log.reimbursement_rate),
        "reimbursement_amount": float(log.reimbursement_amount),
    }


@router.get("/logs")
def list_logs(
    request: Request,
    year: Optional[int] = None,
    vehicle: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    q = db.query(models.MileageLog).filter(models.MileageLog.tenant_id == tenant_id)
    if year:
        q = q.filter(
            models.MileageLog.trip_date >= date(year, 1, 1),
            models.MileageLog.trip_date <= date(year, 12, 31),
        )
    if vehicle:
        q = q.filter(models.MileageLog.vehicle == vehicle)
    logs = q.order_by(models.MileageLog.trip_date).all()
    return [
        {
            "id": log.id,
            "trip_date": log.trip_date.isoformat(),
            "description": log.description,
            "starting_odometer": float(log.starting_odometer),
            "ending_odometer": float(log.ending_odometer),
            "miles": float(log.miles),
            "purpose": log.purpose,
            "vehicle": log.vehicle,
            "reimbursement_rate": float(log.reimbursement_rate),
            "reimbursement_amount": float(log.reimbursement_amount),
        }
        for log in logs
    ]


@router.get("/summary")
def mileage_summary(
    request: Request,
    year: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    logs = db.query(models.MileageLog).filter(
        models.MileageLog.tenant_id == tenant_id,
        models.MileageLog.trip_date >= date(year, 1, 1),
        models.MileageLog.trip_date <= date(year, 12, 31),
    ).all()
    total_miles = sum((log.miles or Decimal("0")) for log in logs)
    total_reimbursement = sum((log.reimbursement_amount or Decimal("0")) for log in logs)
    return {
        "year": year,
        "total_miles": float(total_miles),
        "total_reimbursement": float(total_reimbursement),
        "trip_count": len(logs),
    }
