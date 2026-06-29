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


def _update_status(invoice: models.Invoice) -> None:
    """Auto-transition status based on amount_paid and due_date."""
    if invoice.status == "void":
        return
    paid = Decimal(str(invoice.amount_paid or 0))
    total = Decimal(str(invoice.total or 0))
    if paid >= total and total > 0:
        invoice.status = "paid"
    elif paid > 0:
        invoice.status = "open"  # partially paid
    else:
        today = date.today()
        if invoice.due_date and today > invoice.due_date:
            invoice.status = "overdue"
        else:
            invoice.status = "open"


def create_invoice(
    db: Session,
    tenant_id: int,
    user_id: int,
    contact_name: str,
    invoice_number: str,
    issue_date: date,
    due_date: date,
    line_items: list[dict],
    is_bill: bool = False,
    notes: str | None = None,
) -> models.Invoice:
    """Create a customer invoice (A/R) or vendor bill (A/P).

    Optional line-item fields:
      - tax_rate_id: SalesTaxRate id; triggers sales-tax GL posting for invoices.
      - tax_amount: pre-computed tax (computed from rate if omitted).
    """
    total = Decimal("0.00")
    tax_total = Decimal("0.00")
    for line in line_items:
        qty = Decimal(str(line.get("qty", 1)))
        rate = Decimal(str(line.get("rate", 0)))
        net = qty * rate
        line_tax = Decimal("0.00")
        if not is_bill and line.get("tax_rate_id"):
            tax_rate = db.query(models.SalesTaxRate).filter(
                models.SalesTaxRate.id == line["tax_rate_id"],
                models.SalesTaxRate.tenant_id == tenant_id,
            ).first()
            if tax_rate:
                line_tax = Decimal(str(line.get("tax_amount", 0))) or (net * Decimal(str(tax_rate.rate))).quantize(Decimal("0.01"))
                line["tax_rate_id"] = tax_rate.id
        line["amount"] = float(net)
        line["tax_amount"] = float(line_tax)
        total += net + line_tax
        tax_total += line_tax

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
        is_bill=is_bill,
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

    # Sales-tax GL posting for customer invoices with tax.
    if not is_bill and tax_total > 0:
        _post_sales_tax_invoice_gl(db, tenant_id, user_id, invoice, Decimal(str(invoice.total)) - tax_total, tax_total)

    return invoice


def _post_sales_tax_invoice_gl(
    db: Session,
    tenant_id: int,
    user_id: int,
    invoice: models.Invoice,
    net_total: Decimal,
    tax_total: Decimal,
) -> None:
    """Post A/R, Revenue, and Sales Tax Payable GL entries for a taxable invoice."""
    from backend.accounting.coa import create_account
    ar = create_account(db, tenant_id, user_id, 1100, "Accounts Receivable", "asset")
    revenue = create_account(db, tenant_id, user_id, 4000, "Sales Revenue", "income")
    liability = create_account(db, tenant_id, user_id, 2110, "Sales Tax Payable", "liability")
    entries = []
    entries.append(models.GeneralLedgerEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        date=invoice.issue_date or date.today(),
        description=f"Invoice {invoice.invoice_number} - A/R",
        debit_coa_account_id=ar["id"],
        credit_coa_account_id=None,
        amount=invoice.total,
        memo="Sales tax invoice A/R",
        entry_type="regular",
    ))
    entries.append(models.GeneralLedgerEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        date=invoice.issue_date or date.today(),
        description=f"Invoice {invoice.invoice_number} - Revenue",
        debit_coa_account_id=None,
        credit_coa_account_id=revenue["id"],
        amount=net_total,
        memo="Sales tax invoice revenue",
        entry_type="regular",
    ))
    entries.append(models.GeneralLedgerEntry(
        tenant_id=tenant_id,
        user_id=user_id,
        date=invoice.issue_date or date.today(),
        description=f"Invoice {invoice.invoice_number} - Sales Tax Payable",
        debit_coa_account_id=None,
        credit_coa_account_id=liability["id"],
        amount=tax_total,
        memo="Sales tax liability",
        entry_type="regular",
    ))
    db.add_all(entries)
    db.commit()


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
    return create_invoice(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        contact_name=contact_name,
        invoice_number=invoice_number,
        issue_date=issue_date,
        due_date=due_date,
        line_items=line_items,
        is_bill=True,
    )


def get_invoice(db: Session, invoice_id: int, user_id: int) -> models.Invoice | None:
    """Fetch a single invoice by ID."""
    return db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == user_id,
    ).first()


def update_invoice(
    db: Session,
    invoice_id: int,
    user_id: int,
    contact_name: str | None = None,
    issue_date: date | None = None,
    due_date: date | None = None,
    line_items: list[dict] | None = None,
) -> models.Invoice:
    """Update a draft invoice. Only draft status can be edited."""
    invoice = get_invoice(db, invoice_id, user_id)
    if invoice is None:
        raise InvoicingError("Invoice not found")
    if invoice.status not in ("draft", "open"):
        raise InvoicingError(f"Cannot edit invoice in '{invoice.status}' status")
    if contact_name is not None:
        invoice.contact_name = contact_name
    if issue_date is not None:
        invoice.issue_date = issue_date
    if due_date is not None:
        invoice.due_date = due_date
    if line_items is not None:
        # Replace line items
        db.query(models.InvoiceLineItem).filter(
            models.InvoiceLineItem.invoice_id == invoice_id
        ).delete()
        total = Decimal("0.00")
        for line in line_items:
            qty = Decimal(str(line.get("qty", 1)))
            rate = Decimal(str(line.get("rate", 0)))
            amt = qty * rate
            total += amt
            db_line = models.InvoiceLineItem(
                invoice_id=invoice_id,
                description=line.get("description", ""),
                qty=line.get("qty", 1),
                rate=line.get("rate", 0),
                amount=float(amt),
            )
            db.add(db_line)
        invoice.total = total
    _update_status(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def void_invoice(db: Session, invoice_id: int, user_id: int) -> models.Invoice:
    """Void an invoice/bill. Keeps the record for audit trail."""
    invoice = get_invoice(db, invoice_id, user_id)
    if invoice is None:
        raise InvoicingError("Invoice not found")
    if invoice.status == "void":
        raise InvoicingError("Invoice already voided")
    invoice.status = "void"
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice(db: Session, invoice_id: int, user_id: int) -> bool:
    """Delete a draft invoice. Only drafts can be deleted."""
    invoice = get_invoice(db, invoice_id, user_id)
    if invoice is None:
        raise InvoicingError("Invoice not found")
    if invoice.status not in ("draft", "open"):
        raise InvoicingError(f"Cannot delete invoice in '{invoice.status}' status")
    if invoice.amount_paid and invoice.amount_paid > 0:
        raise InvoicingError("Cannot delete invoice with payments")
    db.query(models.Payment).filter(models.Payment.invoice_id == invoice_id).delete()
    db.query(models.InvoiceLineItem).filter(models.InvoiceLineItem.invoice_id == invoice_id).delete()
    db.delete(invoice)
    db.commit()
    return True


def record_payment(
    db: Session,
    invoice_id: int,
    user_id: int,
    amount: Decimal,
    payment_date: date,
    method: str = "manual",
    notes: str | None = None,
) -> models.Invoice:
    """Record a partial or full payment against an invoice or bill."""
    invoice = get_invoice(db, invoice_id, user_id)
    if invoice is None:
        raise InvoicingError("Invoice not found")
    if invoice.status == "void":
        raise InvoicingError("Cannot record payment on void invoice")
    balance = invoice.total - (invoice.amount_paid or Decimal("0.00"))
    if amount > balance:
        raise InvoicingError("Payment exceeds outstanding balance")
    if amount <= 0:
        raise InvoicingError("Payment amount must be positive")
    invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + amount
    _update_status(invoice)
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


def reverse_payment(
    db: Session,
    invoice_id: int,
    payment_id: int,
    user_id: int,
) -> models.Invoice:
    """Reverse (delete) a payment and recalc invoice status."""
    payment = db.query(models.Payment).filter(
        models.Payment.id == payment_id,
        models.Payment.invoice_id == invoice_id,
    ).first()
    if payment is None:
        raise InvoicingError("Payment not found")
    invoice = get_invoice(db, invoice_id, user_id)
    if invoice is None:
        raise InvoicingError("Invoice not found")
    invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) - payment.amount
    if invoice.amount_paid < 0:
        invoice.amount_paid = Decimal("0.00")
    db.delete(payment)
    _update_status(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def list_invoices(
    db: Session,
    user_id: int,
    is_bill: bool = False,
    status: str | None = None,
    contact_name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Return invoices or bills with aging, optionally filtered."""
    q = db.query(models.Invoice).filter(
        models.Invoice.user_id == user_id,
        models.Invoice.is_bill == is_bill,
    )
    if status:
        q = q.filter(models.Invoice.status == status)
    if contact_name:
        q = q.filter(models.Invoice.contact_name.ilike(f"%{contact_name}%"))
    if start_date:
        q = q.filter(models.Invoice.issue_date >= start_date)
    if end_date:
        q = q.filter(models.Invoice.issue_date <= end_date)
    rows = q.order_by(asc(models.Invoice.issue_date)).all()
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
    outstanding = [r for r in rows if r["status"] not in ("paid", "void")]
    buckets = {"current": 0.0, "30": 0.0, "60": 0.0, "90": 0.0, "90+": 0.0}
    for row in outstanding:
        buckets[row["aging_bucket"]] = buckets.get(row["aging_bucket"], 0.0) + row["balance"]
    return {"buckets": buckets, "total_outstanding": sum(buckets.values()), "count": len(outstanding)}
