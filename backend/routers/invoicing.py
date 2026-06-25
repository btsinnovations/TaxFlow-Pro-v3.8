"""Invoicing / A/P / A/R API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models
from backend.accounting.invoicing import (
    InvoicingError,
    create_invoice as create_invoice_logic,
    create_bill as create_bill_logic,
    record_payment as record_payment_logic,
    list_invoices,
    aging_report,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/invoicing", tags=["invoicing"])


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


class LineItem(BaseModel):
    description: str
    qty: float = 1
    rate: float


class InvoiceCreate(BaseModel):
    contact_name: str
    invoice_number: str
    issue_date: date
    due_date: date
    line_items: list[LineItem]


class Payment(BaseModel):
    amount: float
    payment_date: date
    method: str = "manual"


@router.get("/invoices")
def get_invoices(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    return list_invoices(db, user_id=current_user.id, is_bill=False)


@router.get("/bills")
def get_bills(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    return list_invoices(db, user_id=current_user.id, is_bill=True)


@router.post("/invoices", response_model=dict, status_code=201)
def create_invoice(
    request: Request,
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    invoice = create_invoice_logic(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        contact_name=payload.contact_name,
        invoice_number=payload.invoice_number,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        line_items=[li.model_dump() for li in payload.line_items],
    )
    return {"id": invoice.id, "total": float(invoice.total), "status": invoice.status}


@router.post("/bills", response_model=dict, status_code=201)
def create_bill(
    request: Request,
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    bill = create_bill_logic(
        db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        contact_name=payload.contact_name,
        invoice_number=payload.invoice_number,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        line_items=[li.model_dump() for li in payload.line_items],
    )
    return {"id": bill.id, "total": float(bill.total), "status": bill.status, "is_bill": True}


@router.post("/{invoice_id}/payments", response_model=dict)
def record_payment(
    request: Request,
    invoice_id: int,
    payload: Payment,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    try:
        invoice = record_payment_logic(
            db,
            invoice_id=invoice_id,
            user_id=current_user.id,
            amount=Decimal(str(payload.amount)),
            payment_date=payload.payment_date,
            method=payload.method,
        )
    except InvoicingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": invoice.id,
        "total": float(invoice.total),
        "amount_paid": float(invoice.amount_paid),
        "status": invoice.status,
    }


@router.get("/aging")
def aging(
    request: Request,
    is_bill: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    return aging_report(db, user_id=current_user.id, is_bill=is_bill)
