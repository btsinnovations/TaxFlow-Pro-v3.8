"""
Exchange rate router: manage currency exchange rates with filters,
bulk import, and currency conversion endpoint.
"""
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/exchange-rates", tags=["exchange_rates"])


class RateConvertRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    rate_date: Optional[str] = None


class RateConvertResponse(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    converted_amount: float
    rate: float
    rate_date: str


class BulkRateItem(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    rate_date: str
    source: str = "import"


class BulkImportRequest(BaseModel):
    rates: List[BulkRateItem]


@router.get("", response_model=List[schemas.ExchangeRate])
def list_rates(
    client_id: int = Query(..., description="Client ID (tenant)"),
    from_currency: Optional[str] = Query(None),
    to_currency: Optional[str] = Query(None),
    rate_date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.tenant_id == client_id
    )

    if from_currency:
        query = query.filter(
            models.ExchangeRate.from_currency == from_currency.upper()
        )
    if to_currency:
        query = query.filter(
            models.ExchangeRate.to_currency == to_currency.upper()
        )
    if rate_date:
        query = query.filter(models.ExchangeRate.rate_date == rate_date)
    if source:
        query = query.filter(models.ExchangeRate.source == source)

    rates = (
        query.order_by(models.ExchangeRate.rate_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rates


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.ExchangeRate)
def create_or_update_rate(
    client_id: int = Query(..., description="Client ID (tenant)"),
    data: schemas.ExchangeRateCreate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if data.rate <= 0:
        raise HTTPException(status_code=400, detail="Rate must be positive")

    # Check if rate already exists for same date/currency pair
    existing = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.tenant_id == client_id,
            models.ExchangeRate.from_currency == data.from_currency.upper(),
            models.ExchangeRate.to_currency == data.to_currency.upper(),
            models.ExchangeRate.rate_date == data.rate_date,
        )
        .first()
    )

    if existing:
        existing.rate = data.rate
        existing.source = data.source
        db.commit()
        db.refresh(existing)
        audit = models.AuditEntry(
            tenant_id=client_id,
            user_id=current_user.id,
            action="exchange_rate_update",
            entity_type="exchange_rate",
            entity_id=existing.id,
            details=f"Updated rate {data.from_currency}/{data.to_currency} = {data.rate} on {data.rate_date}",
        )
        db.add(audit)
        db.commit()
        return existing

    rate = models.ExchangeRate(
        tenant_id=client_id,
        from_currency=data.from_currency.upper(),
        to_currency=data.to_currency.upper(),
        rate=data.rate,
        rate_date=data.rate_date,
        source=data.source,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="exchange_rate_create",
        entity_type="exchange_rate",
        entity_id=rate.id,
        details=f"Created rate {data.from_currency}/{data.to_currency} = {data.rate} on {data.rate_date}",
    )
    db.add(audit)
    db.commit()

    return rate


@router.post("/import", status_code=status.HTTP_200_OK)
def bulk_import_rates(
    client_id: int = Query(..., description="Client ID (tenant)"),
    data: BulkImportRequest = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    created = 0
    updated = 0
    errors = []

    for item in data.rates:
        if item.rate <= 0:
            errors.append(f"Invalid rate for {item.from_currency}/{item.to_currency}: {item.rate}")
            continue

        existing = (
            db.query(models.ExchangeRate)
            .filter(
                models.ExchangeRate.tenant_id == client_id,
                models.ExchangeRate.from_currency == item.from_currency.upper(),
                models.ExchangeRate.to_currency == item.to_currency.upper(),
                models.ExchangeRate.rate_date == item.rate_date,
            )
            .first()
        )

        if existing:
            existing.rate = item.rate
            existing.source = item.source
            updated += 1
        else:
            rate = models.ExchangeRate(
                tenant_id=client_id,
                from_currency=item.from_currency.upper(),
                to_currency=item.to_currency.upper(),
                rate=item.rate,
                rate_date=item.rate_date,
                source=item.source,
            )
            db.add(rate)
            created += 1

    db.commit()

    audit = models.AuditEntry(
        tenant_id=client_id,
        user_id=current_user.id,
        action="exchange_rate_bulk_import",
        entity_type="exchange_rate",
        entity_id=client_id,
        details=f"Bulk import: {created} created, {updated} updated, {len(errors)} errors",
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Bulk import completed",
        "created": created,
        "updated": updated,
        "errors": errors if errors else None,
    }


@router.get("/convert", response_model=RateConvertResponse)
def convert_currency(
    client_id: int = Query(..., description="Client ID (tenant)"),
    from_currency: str = Query(..., description="Source currency code"),
    to_currency: str = Query(..., description="Target currency code"),
    amount: float = Query(..., gt=0, description="Amount to convert"),
    rate_date: Optional[str] = Query(None, description="Specific date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = (
        db.query(models.Client)
        .filter(models.Client.id == client_id)
        .first()
    )
    if not client or client.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    fc = from_currency.upper()
    tc = to_currency.upper()

    query = (
        db.query(models.ExchangeRate)
        .filter(
            models.ExchangeRate.tenant_id == client_id,
            models.ExchangeRate.from_currency == fc,
            models.ExchangeRate.to_currency == tc,
        )
    )
    if rate_date:
        query = query.filter(models.ExchangeRate.rate_date == rate_date)

    rate = query.order_by(models.ExchangeRate.rate_date.desc()).first()

    if not rate:
        # Try inverse rate
        inv_query = (
            db.query(models.ExchangeRate)
            .filter(
                models.ExchangeRate.tenant_id == client_id,
                models.ExchangeRate.from_currency == tc,
                models.ExchangeRate.to_currency == fc,
            )
        )
        if rate_date:
            inv_query = inv_query.filter(models.ExchangeRate.rate_date == rate_date)
        inv_rate = inv_query.order_by(models.ExchangeRate.rate_date.desc()).first()

        if inv_rate:
            converted = amount / float(inv_rate.rate)
            return RateConvertResponse(
                from_currency=fc,
                to_currency=tc,
                amount=amount,
                converted_amount=round(converted, 8),
                rate=round(1.0 / float(inv_rate.rate), 8),
                rate_date=inv_rate.rate_date,
            )

        raise HTTPException(
            status_code=404,
            detail=f"No exchange rate found for {fc}/{tc}",
        )

    converted = amount * float(rate.rate)
    return RateConvertResponse(
        from_currency=fc,
        to_currency=tc,
        amount=amount,
        converted_amount=round(converted, 8),
        rate=float(rate.rate),
        rate_date=rate.rate_date,
    )
