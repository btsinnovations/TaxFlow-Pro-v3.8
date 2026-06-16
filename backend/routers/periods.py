"""
Period management router for TaxFlow Pro v3.8.

Provides CRUD for accounting periods, lock/unlock operations with
warnings about unconfirmed transactions, and date-in-locked-period
checks.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id
from ..audit.audit_trail import (
    create_audit_entry,
    ACTION_LOCK_PERIOD,
    ACTION_UNLOCK_PERIOD,
)
from .auth import get_current_user

router = APIRouter(prefix="/periods", tags=["periods"])


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=schemas.Period, status_code=status.HTTP_201_CREATED)
def create_period(
    request: Request,
    period: schemas.PeriodCreate,
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a new accounting period for a client/year.
    *client_id* query param is required.
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    # Validate date ordering
    if period.end_date < period.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date.",
        )

    # Check for overlapping period
    overlap = (
        db.query(models.Period)
        .filter(
            models.Period.tenant_id == tenant_id,
            models.Period.start_date <= period.end_date,
            models.Period.end_date >= period.start_date,
        )
        .first()
    )
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Period overlaps with existing '{overlap.name}' ({overlap.start_date} to {overlap.end_date}).",
        )

    db_period = models.Period(
        tenant_id=tenant_id,
        user_id=current_user.id,
        name=period.name,
        start_date=period.start_date,
        end_date=period.end_date,
        status=period.status,
        is_locked=period.is_locked,
    )
    db.add(db_period)
    db.commit()
    db.refresh(db_period)
    return db_period


@router.get("/", response_model=List[schemas.Period])
def list_periods(
    request: Request,
    client_id: int,
    year: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List accounting periods for a client.  Filter by year optionally."""
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    query = db.query(models.Period).filter(
        models.Period.tenant_id == tenant_id,
        models.Period.user_id == current_user.id,
    )

    if year:
        query = query.filter(
            models.Period.start_date >= f"{year}-01-01",
            models.Period.end_date <= f"{year}-12-31",
        )

    return (
        query.order_by(models.Period.start_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("/{period_id}/lock")
def lock_period(
    request: Request,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Lock an accounting period.

    Warns if there are unconfirmed transactions within the period
    but allows the lock to proceed regardless.
    """
    _wrap_tenant(request, db)
    period = (
        db.query(models.Period)
        .filter(
            models.Period.id == period_id,
            models.Period.user_id == current_user.id,
        )
        .first()
    )
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Period not found",
        )

    if period.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Period is already locked.",
        )

    # Check for unconfirmed transactions in period range
    unconfirmed_count = (
        db.query(func.count(models.Transaction.id))
        .filter(
            models.Transaction.tenant_id == period.tenant_id,
            models.Transaction.date >= period.start_date,
            models.Transaction.date <= period.end_date,
            models.Transaction.confirmed == False,
            models.Transaction.archived == False,
        )
        .scalar()
    )

    period.is_locked = True
    period.status = "locked"
    db.commit()
    db.refresh(period)

    # Audit trail
    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_LOCK_PERIOD,
        entity_type="Period",
        entity_id=period.id,
        new_values={
            "name": period.name,
            "start_date": period.start_date,
            "end_date": period.end_date,
            "unconfirmed_transactions": unconfirmed_count,
        },
        client_id=period.tenant_id,
    )
    db.commit()

    response = {
        "ok": True,
        "period_id": period.id,
        "is_locked": True,
    }
    if unconfirmed_count and unconfirmed_count > 0:
        response["warning"] = (
            f"Period locked with {unconfirmed_count} unconfirmed transaction(s) "
            f"in the date range {period.start_date} to {period.end_date}."
        )

    return response


@router.post("/{period_id}/unlock")
def unlock_period(
    request: Request,
    period_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Unlock a previously locked accounting period."""
    _wrap_tenant(request, db)
    period = (
        db.query(models.Period)
        .filter(
            models.Period.id == period_id,
            models.Period.user_id == current_user.id,
        )
        .first()
    )
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Period not found",
        )

    if not period.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Period is not locked.",
        )

    period.is_locked = False
    period.status = "open"
    db.commit()
    db.refresh(period)

    # Audit trail
    create_audit_entry(
        db=db,
        user_id=current_user.id,
        action=ACTION_UNLOCK_PERIOD,
        entity_type="Period",
        entity_id=period.id,
        old_values={"is_locked": True, "status": "locked"},
        new_values={"is_locked": False, "status": "open"},
        client_id=period.tenant_id,
    )
    db.commit()

    return {"ok": True, "period_id": period.id, "is_locked": False}


@router.get("/check")
def check_date_locked(
    request: Request,
    client_id: int,
    date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Check if a given date falls within a locked period for a client.

    Returns ``locked: true`` and the matching period details if locked,
    otherwise ``locked: false``.
    """
    _wrap_tenant(request, db)
    tenant_id = _get_tenant_id(request, client_id)

    period = (
        db.query(models.Period)
        .filter(
            models.Period.tenant_id == tenant_id,
            models.Period.is_locked == True,
            models.Period.start_date <= date,
            models.Period.end_date >= date,
        )
        .first()
    )

    if period:
        return {
            "locked": True,
            "period": {
                "id": period.id,
                "name": period.name,
                "start_date": period.start_date,
                "end_date": period.end_date,
            },
        }

    return {"locked": False, "period": None}
