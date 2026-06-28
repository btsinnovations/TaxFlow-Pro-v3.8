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
    """Return annual 1099-NEC/MISC candidates grouped by payee description.

    This is a pragmatic approximation: transactions whose description is
    treated as the payee name and whose debit amount exceeds the threshold are
    surfaced as 1099 candidates. In production this should be keyed off vendor
    records.
    """
    txns = _1099_candidates(db, tenant_id, user_id, year)
    payee_totals: dict[str, Decimal] = {}
    for t in txns:
        payee = (t.description or "Unknown").strip()
        payee_totals[payee] = payee_totals.get(payee, Decimal("0")) + Decimal(str(t.amount or 0))

    results = []
    for payee, total in payee_totals.items():
        if total >= threshold:
            # Classify as NEC (nonemployee compensation) for contract-labor-like
            # descriptions; otherwise MISC.
            form = "1099-NEC" if any(
                kw in payee.lower() for kw in ("contractor", "freelance", "consultant", "contract labor")
            ) else "1099-MISC"
            results.append({
                "payee": payee,
                "form": form,
                "year": year,
                "amount": float(total),
            })
    results.sort(key=lambda r: (-r["amount"], r["payee"]))
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
