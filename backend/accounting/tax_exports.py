"""Tax filing export domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


SCHEDULE_C_LINES = {
    "income": "1",
    "returns": "2",
    "other_income": "6",
    "advertising": "8",
    "car": "9",
    "commissions": "10",
    "contract_labor": "11",
    "depletion": "12",
    "depreciation": "13",
    "employee_benefits": "14",
    "insurance": "15",
    "interest": "16",
    "mortgage": "16a",
    "other": "16b",
    "legal": "17",
    "office": "18",
    "pension": "19",
    "rent": "20a",
    "repairs": "21",
    "supplies": "22",
    "taxes": "23",
    "travel": "24a",
    "meals": "24b",
    "utilities": "25",
    "wages": "26",
    "other_expenses": "27a",
}


def _txns_for_period(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[models.Transaction]:
    return db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == user_id,
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
    ).all()


def _txn_signed_income_expense(txn: models.Transaction) -> tuple[Decimal, Decimal]:
    amt = Decimal(str(txn.amount or 0))
    tx_type = (txn.tx_type or "").lower()
    if tx_type in ("credit", "deposit", "income"):
        return (amt, Decimal("0"))
    return (Decimal("0"), amt)


def schedule_c(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate a Schedule C-style summary for the period.

    Uses TaxLineMapping to roll up income/expense by line. Transactions
    without a mapping fall back to the aggregate line_1 / line_28 totals.
    """
    txns = _txns_for_period(db, tenant_id, user_id, start_date, end_date)
    mappings = {
        m.coa_account_id: m for m in db.query(models.TaxLineMapping).filter(
            models.TaxLineMapping.tenant_id == tenant_id,
            models.TaxLineMapping.user_id == user_id,
            models.TaxLineMapping.form == "Schedule C",
        ).all()
    }

    line_income: dict[str, Decimal] = {}
    line_expense: dict[str, Decimal] = {}
    fallback_income = Decimal("0")
    fallback_expenses = Decimal("0")

    for t in txns:
        inc, exp = _txn_signed_income_expense(t)
        mapping = mappings.get(t.coa_account_id)
        if mapping:
            line = mapping.line
            if inc > 0:
                line_income[line] = line_income.get(line, Decimal("0")) + inc
            if exp > 0:
                line_expense[line] = line_expense.get(line, Decimal("0")) + exp
        else:
            fallback_income += inc
            fallback_expenses += exp

    total_income = sum(line_income.values(), Decimal("0")) + fallback_income
    total_expenses = sum(line_expense.values(), Decimal("0")) + fallback_expenses

    return {
        "form": "Schedule C",
        "year": start_date.year,
        "line_1_gross_receipts": float(total_income),
        "line_28_total_expenses": float(total_expenses),
        "line_31_net_profit": float(total_income - total_expenses),
        "lines": {
            "income": {k: float(v) for k, v in line_income.items()},
            "expense": {k: float(v) for k, v in line_expense.items()},
        },
        "generated_at": date.today().isoformat(),
    }


def schedule_c_csv(result: dict) -> str:
    """Render a Schedule C result as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["form", "year", "line", "description", "amount"])
    writer.writerow([result["form"], result["year"], "1", "Gross receipts", result["line_1_gross_receipts"]])
    writer.writerow([result["form"], result["year"], "28", "Total expenses", result["line_28_total_expenses"]])
    writer.writerow([result["form"], result["year"], "31", "Net profit", result["line_31_net_profit"]])
    for line, amount in result["lines"]["income"].items():
        writer.writerow([result["form"], result["year"], line, "Income", amount])
    for line, amount in result["lines"]["expense"].items():
        writer.writerow([result["form"], result["year"], line, "Expense", amount])
    return output.getvalue()


def _1099_candidates(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
) -> list[models.Transaction]:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == user_id,
        models.Transaction.date >= start,
        models.Transaction.date <= end,
        models.Transaction.tx_type.ilike("debit"),
    ).all()


def form_1099_nec_misc(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
    threshold: Decimal = Decimal("600"),
) -> list[dict]:
    """Return annual 1099-NEC/MISC candidates grouped by vendor record.

    Falls back to transaction description grouping only when no vendor records
    are present. Vendors marked is_1099_eligible are prioritised; all vendors
    paid >= threshold are still returned.
    """
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    # Vendor-keyed payments via invoices/bills (vendor_id on Payment is not
    # yet present, so derive from bill contact_name -> vendor name).
    vendors = db.query(models.Vendor).filter(
        models.Vendor.tenant_id == tenant_id,
    ).all()
    vendor_map = {v.name.strip().lower(): v for v in vendors}

    # Vendor-keyed payments via invoices/bills (paid bills in the tax year).
    bills = db.query(models.Invoice).filter(
        models.Invoice.tenant_id == tenant_id,
        models.Invoice.user_id == user_id,
        models.Invoice.is_bill == True,
        models.Invoice.issue_date >= start,
        models.Invoice.issue_date <= end,
    ).all()

    vendor_totals: dict[int, Decimal] = {}
    fallback_totals: dict[str, Decimal] = {}

    for bill in bills:
        paid = Decimal(str(bill.amount_paid or 0))
        if paid == 0:
            continue
        vendor = vendor_map.get((bill.contact_name or "").strip().lower())
        if vendor:
            vendor_totals[vendor.id] = vendor_totals.get(vendor.id, Decimal("0")) + paid
        else:
            name = (bill.contact_name or "Unknown").strip()
            fallback_totals[name] = fallback_totals.get(name, Decimal("0")) + paid

    # Fallback to debit transactions grouped by description when no matching
    # vendor record exists. This preserves legacy 1099 detection from bank txns.
    txns = _1099_candidates(db, tenant_id, user_id, year)
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        name = (t.description or "Unknown").strip()
        # Skip if this transaction's description already matched a vendor via bills.
        if name.lower() in vendor_map:
            continue
        fallback_totals[name] = fallback_totals.get(name, Decimal("0")) + amt

    results = []
    for vendor_id, total in vendor_totals.items():
        if total >= threshold:
            vendor = next((v for v in vendors if v.id == vendor_id), None)
            if not vendor:
                continue
            form = "1099-NEC" if vendor.is_1099_eligible else "1099-MISC"
            results.append({
                "vendor_id": vendor.id,
                "payee": vendor.name,
                "tin": vendor.tax_id,
                "form": form,
                "year": year,
                "amount": float(total),
                "is_vendor": True,
            })
    for name, total in fallback_totals.items():
        if total >= threshold:
            form = "1099-NEC" if any(
                kw in name.lower() for kw in ("contractor", "freelance", "consultant", "contract labor")
            ) else "1099-MISC"
            results.append({
                "payee": name,
                "form": form,
                "year": year,
                "amount": float(total),
                "is_vendor": False,
            })
    results.sort(key=lambda r: (-r["amount"], r.get("payee", "")))
    return results


def year_end_summary(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
) -> dict:
    """Return a year-end tax package: Schedule C + 1099s + P&L totals."""
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    schedule_c_result = schedule_c(db, tenant_id, user_id, start, end)
    form_1099s = form_1099_nec_misc(db, tenant_id, user_id, year)

    return {
        "year": year,
        "schedule_c": schedule_c_result,
        "form_1099s": form_1099s,
        "total_reported_1099": float(sum(Decimal(str(r["amount"])) for r in form_1099s)),
        "generated_at": date.today().isoformat(),
    }


def set_mapping(
    db: Session,
    tenant_id: int,
    user_id: int,
    coa_account_id: int,
    form: str,
    line: str,
    description: Optional[str] = None,
) -> models.TaxLineMapping:
    """Map a COA account to a tax form line."""
    existing = db.query(models.TaxLineMapping).filter(
        models.TaxLineMapping.tenant_id == tenant_id,
        models.TaxLineMapping.user_id == user_id,
        models.TaxLineMapping.coa_account_id == coa_account_id,
        models.TaxLineMapping.form == form,
    ).first()
    if existing is not None:
        existing.line = line
        existing.description = description
        db.commit()
        db.refresh(existing)
        return existing

    mapping = models.TaxLineMapping(
        tenant_id=tenant_id,
        user_id=user_id,
        coa_account_id=coa_account_id,
        form=form,
        line=line,
        description=description,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def delete_mapping(
    db: Session,
    tenant_id: int,
    user_id: int,
    mapping_id: int,
) -> bool:
    """Delete a tax line mapping if owned by the user/tenant."""
    mapping = db.query(models.TaxLineMapping).filter(
        models.TaxLineMapping.id == mapping_id,
        models.TaxLineMapping.tenant_id == tenant_id,
        models.TaxLineMapping.user_id == user_id,
    ).first()
    if mapping is None:
        return False
    db.delete(mapping)
    db.commit()
    return True


def list_mappings(db: Session, tenant_id: int, user_id: int) -> list[models.TaxLineMapping]:
    return db.query(models.TaxLineMapping).filter(
        models.TaxLineMapping.tenant_id == tenant_id,
        models.TaxLineMapping.user_id == user_id,
    ).order_by(models.TaxLineMapping.form, models.TaxLineMapping.line).all()
