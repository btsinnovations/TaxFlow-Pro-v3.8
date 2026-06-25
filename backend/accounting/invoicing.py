"""Lightweight invoicing / A/P / A/R domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc

from .. import models


class InvoicingError(Exception):
    """Domain error for invoice/bill operations."""


def _aging_bucket(days_overdue: int | None) -> str:
    if days_overdue is None or days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "30"
    if days_overdue <= 60:
        return "60"
    if days_overdue <= 90:
        return "90"
    return "90+"


def create_invoice(
    db: Session,
    tenant_id: int,
    user_id: int,
    contact_name: str,
    invoice_number: str,
    issue_date: date,
    due_date: date,
    line_items: list[dict],
) -> models.Invoice:
    """Create a customer invoice (A/R)."""
    total = Decimal("0.00")
    for line in line_items:
        qty = Decimal(str(line.get("qty", 1)))
        rate = Decimal(str(line.get("rate", 0)))
        line["amount"] = float(qty * rate)
        total += qty * rate

    invoice = models.Invoice(
        tenant_id=tenant_id,
        user_id=user_id,
        contact_name=contact_name,
        invoice_number=invoice_number,
        issue_date=issue_date,
        due_date=due_date,
        total=total,
        amount_paid=Decimal("0.00"),
        status="open",
        is_bill=False,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    for line in line_items:
        db_line = models.InvoiceLineItem(
            invoice_id=invoice.id,
            description=line.get("description", ""),
            qty=line.get("qty", 1),
            rate=line.get("rate", 0),
            amount=line["amount"],
        )
        db.add(db_line)
    db.commit()
    db.refresh(invoice)
    return invoice


def create_bill(
    db: Session,
    tenant_id: int,
    user_id: int,
    contact_name: str,
    invoice_number: str,
    issue_date: date,
    due_date: date,
    line_items: list[dict],
) -> models.Invoice:
    """Create a vendor bill (A/P)."""
    invoice = create_invoice(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        contact_name=contact_name,
        invoice_number=invoice_number,
        issue_date=issue_date,
        due_date=due_date,
        line_items=line_items,
    )
    invoice.is_bill = True
    invoice.status = "open"
    db.commit()
    db.refresh(invoice)
    return invoice


def record_payment(
    db: Session,
    invoice_id: int,
    user_id: int,
    amount: Decimal,
    payment_date: date,
    method: str = "manual",
) -> models.Invoice:
    """Record a partial or full payment against an invoice or bill."""
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == user_id,
    ).first()
    if invoice is None:
        raise InvoicingError("Invoice not found")
    balance = invoice.total - (invoice.amount_paid or Decimal("0.00"))
    if amount > balance:
        raise InvoicingError("Payment exceeds outstanding balance")
    invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + amount
    if invoice.amount_paid >= invoice.total:
        invoice.status = "paid"
    payment = models.Payment(
        invoice_id=invoice_id,
        date=payment_date,
        amount=amount,
        method=method,
    )
    db.add(payment)
    db.commit()
    db.refresh(invoice)
    return invoice


def list_invoices(db: Session, user_id: int, is_bill: bool = False) -> list[dict]:
    """Return invoices or bills with aging."""
    rows = db.query(models.Invoice).filter(
        models.Invoice.user_id == user_id,
        models.Invoice.is_bill == is_bill,
    ).order_by(asc(models.Invoice.issue_date)).all()
    today = date.today()
    result = []
    for inv in rows:
        days_overdue = (today - inv.due_date).days if inv.due_date else None
        result.append({
            "id": inv.id,
            "contact_name": inv.contact_name,
            "invoice_number": inv.invoice_number,
            "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "total": float(inv.total),
            "amount_paid": float(inv.amount_paid or Decimal("0.00")),
            "balance": float(inv.total - (inv.amount_paid or Decimal("0.00"))),
            "status": inv.status,
            "aging_bucket": _aging_bucket(days_overdue),
        })
    return result


def aging_report(db: Session, user_id: int, is_bill: bool = False) -> dict:
    """Group outstanding invoices/bills by aging bucket."""
    rows = list_invoices(db, user_id, is_bill=is_bill)
    outstanding = [r for r in rows if r["status"] != "paid"]
    buckets = {"current": 0.0, "30": 0.0, "60": 0.0, "90": 0.0, "90+": 0.0}
    for row in outstanding:
        buckets[row["aging_bucket"]] = buckets.get(row["aging_bucket"], 0.0) + row["balance"]
    return {"buckets": buckets, "total_outstanding": sum(buckets.values()), "count": len(outstanding)}
