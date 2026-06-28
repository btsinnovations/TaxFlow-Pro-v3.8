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
    reverse_payment as reverse_payment_logic,
    list_invoices,
    aging_report,
    get_invoice,
    update_invoice as update_invoice_logic,
    void_invoice as void_invoice_logic,
    delete_invoice as delete_invoice_logic,
)
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings
from backend.local.roles import Role, has_role

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


def _require_role(db: Session, current_user: models.User, tenant_id: int, min_role: Role):
    if not has_role(db, current_user.id, tenant_id, min_role):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient profile role ({min_role.name} required)",
        )


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


class InvoiceUpdate(BaseModel):
    contact_name: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    line_items: list[LineItem] | None = None


class PaymentRequest(BaseModel):
    amount: float
    payment_date: date
    method: str = "manual"


@router.get("/invoices")
def get_invoices(
    request: Request,
    status: str | None = None,
    contact: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return list_invoices(db, user_id=current_user.id, is_bill=False,
                        status=status, contact_name=contact,
                        start_date=start_date, end_date=end_date)


@router.get("/bills")
def get_bills(
    request: Request,
    status: str | None = None,
    contact: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return list_invoices(db, user_id=current_user.id, is_bill=True,
                        status=status, contact_name=contact,
                        start_date=start_date, end_date=end_date)


@router.post("/invoices", response_model=dict, status_code=201)
def create_invoice(
    request: Request,
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
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
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
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


@router.get("/aging")
def aging(
    request: Request,
    is_bill: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    return aging_report(db, user_id=current_user.id, is_bill=is_bill)


@router.get("/{invoice_id}")
def get_single_invoice(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.viewer)
    invoice = get_invoice(db, invoice_id, current_user.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    line_items = [
        {"id": li.id, "description": li.description, "qty": float(li.qty),
         "rate": float(li.rate), "amount": float(li.amount)}
        for li in invoice.line_items
    ]
    payments = [
        {"id": p.id, "date": p.date.isoformat(), "amount": float(p.amount), "method": p.method}
        for p in invoice.payments
    ]
    return {
        "id": invoice.id,
        "contact_name": invoice.contact_name,
        "invoice_number": invoice.invoice_number,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "total": float(invoice.total),
        "amount_paid": float(invoice.amount_paid or 0),
        "balance": float(invoice.total - (invoice.amount_paid or 0)),
        "status": invoice.status,
        "is_bill": invoice.is_bill,
        "line_items": line_items,
        "payments": payments,
    }


@router.put("/{invoice_id}")
def update_invoice(
    request: Request,
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    try:
        invoice = update_invoice_logic(
            db,
            invoice_id=invoice_id,
            user_id=current_user.id,
            contact_name=payload.contact_name,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            line_items=[li.model_dump() for li in payload.line_items] if payload.line_items else None,
        )
    except InvoicingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": invoice.id, "total": float(invoice.total), "status": invoice.status}


@router.delete("/{invoice_id}")
def delete_invoice_endpoint(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.admin)
    try:
        delete_invoice_logic(db, invoice_id, current_user.id)
    except InvoicingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/{invoice_id}/void")
def void_invoice(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
    try:
        invoice = void_invoice_logic(db, invoice_id, current_user.id)
    except InvoicingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": invoice.id, "status": invoice.status}


@router.post("/{invoice_id}/payments", response_model=dict)
def record_payment(
    request: Request,
    invoice_id: int,
    payload: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.bookkeeper)
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


@router.delete("/{invoice_id}/payments/{payment_id}")
def reverse_payment(
    request: Request,
    invoice_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_id = _wrap_tenant(request, db, current_user)
    _require_role(db, current_user, tenant_id, Role.admin)
    try:
        invoice = reverse_payment_logic(db, invoice_id, payment_id, current_user.id)
    except InvoicingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": invoice.id,
        "amount_paid": float(invoice.amount_paid),
        "status": invoice.status,
    }



