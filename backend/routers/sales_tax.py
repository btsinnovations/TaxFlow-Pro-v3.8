"""Sales tax tracking API for TaxFlow Pro v3.11.6."""
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
from backend.accounting.gl_bridge import GLBridge

router = APIRouter(prefix="/sales-tax", tags=["sales-tax"])


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


class SalesTaxRateCreate(BaseModel):
    name: str
    jurisdiction: str
    rate: float
    effective_date: date
    is_active: Optional[bool] = True


class SalesTaxPaymentCreate(BaseModel):
    period_start: date
    period_end: date
    payment_date: date
    amount: float
    jurisdiction: Optional[str] = None


def _get_or_create_liability_coa(db: Session, tenant_id: int, user_id: int, number: int, name: str):
    existing = db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
        models.CoaAccount.number == number,
    ).first()
    if existing:
        return existing
    account = models.CoaAccount(
        tenant_id=tenant_id,
        number=number,
        name=name,
        type="liability",
    )
    db.add(account)
    db.flush()
    return account


@router.post("/rates", response_model=dict, status_code=201)
def create_rate(
    request: Request,
    payload: SalesTaxRateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Bookkeeper role required")
    rate = models.SalesTaxRate(
        tenant_id=tenant_id,
        user_id=current_user.id,
        name=payload.name,
        jurisdiction=payload.jurisdiction,
        rate=Decimal(str(payload.rate)),
        effective_date=payload.effective_date,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return {
        "id": rate.id,
        "name": rate.name,
        "jurisdiction": rate.jurisdiction,
        "rate": float(rate.rate),
        "effective_date": rate.effective_date.isoformat(),
        "is_active": rate.is_active,
    }


@router.get("/rates")
def list_rates(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    rates = db.query(models.SalesTaxRate).filter(
        models.SalesTaxRate.tenant_id == tenant_id,
    ).order_by(models.SalesTaxRate.jurisdiction, models.SalesTaxRate.effective_date.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "jurisdiction": r.jurisdiction,
            "rate": float(r.rate),
            "effective_date": r.effective_date.isoformat(),
            "is_active": r.is_active,
        }
        for r in rates
    ]


@router.post("/payments", response_model=dict, status_code=201)
def record_payment(
    request: Request,
    payload: SalesTaxPaymentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.bookkeeper):
        raise HTTPException(status_code=403, detail="Bookkeeper role required")

    liability_coa = _get_or_create_liability_coa(db, tenant_id, current_user.id, 2110, "Sales Tax Payable")

    payment = models.SalesTaxPayment(
        tenant_id=tenant_id,
        user_id=current_user.id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        payment_date=payload.payment_date,
        amount=Decimal(str(payload.amount)),
        jurisdiction=payload.jurisdiction,
    )
    db.add(payment)

    # Post GL entry: debit liability, credit cash/asset.
    asset_coa = db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
        models.CoaAccount.type == "asset",
        models.CoaAccount.number >= 1000,
        models.CoaAccount.number < 2000,
    ).first()
    if asset_coa is None:
        from backend.accounting.coa import NUMBERING_RANGES
        asset_coa = _get_or_create_liability_coa(db, tenant_id, current_user.id, 1020, "Operating Checking")

    gl_entry = models.GeneralLedgerEntry(
        tenant_id=tenant_id,
        user_id=current_user.id,
        date=payload.payment_date,
        description=f"Sales tax payment {payload.period_start} to {payload.period_end}",
        debit_coa_account_id=liability_coa.id,
        credit_coa_account_id=asset_coa.id,
        amount=payment.amount,
        memo="Sales tax remittance",
        entry_type="adjusting",
    )
    db.add(gl_entry)

    db.commit()
    db.refresh(payment)
    return {
        "id": payment.id,
        "period_start": payment.period_start.isoformat(),
        "period_end": payment.period_end.isoformat(),
        "payment_date": payment.payment_date.isoformat(),
        "amount": float(payment.amount),
        "jurisdiction": payment.jurisdiction,
    }


@router.get("/payments")
def list_payments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    payments = db.query(models.SalesTaxPayment).filter(
        models.SalesTaxPayment.tenant_id == tenant_id,
    ).order_by(models.SalesTaxPayment.payment_date.desc()).all()
    return [
        {
            "id": p.id,
            "period_start": p.period_start.isoformat(),
            "period_end": p.period_end.isoformat(),
            "payment_date": p.payment_date.isoformat(),
            "amount": float(p.amount),
            "jurisdiction": p.jurisdiction,
        }
        for p in payments
    ]


@router.get("/liability-summary")
def liability_summary(
    request: Request,
    as_of: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    if not has_role(db, current_user.id, tenant_id, Role.viewer):
        raise HTTPException(status_code=403, detail="Viewer role required")
    effective_date = as_of or date.today()
    # Sum GL entries to liability account 2110.
    liability_coa = db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
        models.CoaAccount.number == 2110,
    ).first()
    if liability_coa is None:
        return {"as_of": effective_date.isoformat(), "collected": 0.0, "remitted": 0.0, "balance": 0.0}

    collected = sum(
        Decimal(str(e.amount or 0))
        for e in db.query(models.GeneralLedgerEntry).filter(
            models.GeneralLedgerEntry.tenant_id == tenant_id,
            models.GeneralLedgerEntry.credit_coa_account_id == liability_coa.id,
            models.GeneralLedgerEntry.date <= effective_date,
        ).all()
    )
    remitted = sum(
        Decimal(str(e.amount or 0))
        for e in db.query(models.GeneralLedgerEntry).filter(
            models.GeneralLedgerEntry.tenant_id == tenant_id,
            models.GeneralLedgerEntry.debit_coa_account_id == liability_coa.id,
            models.GeneralLedgerEntry.date <= effective_date,
        ).all()
    )
    return {
        "as_of": effective_date.isoformat(),
        "collected": float(collected),
        "remitted": float(remitted),
        "balance": float(collected - remitted),
    }
