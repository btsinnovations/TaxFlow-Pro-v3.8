"""Tax filing export domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

import csv
import io
import json
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..accounting.reports import balance_sheet, profit_and_loss, trial_balance
from ..services.depreciation import compute_schedule


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

FORM_1065_LINES = {
    "ordinary_income_loss": "1",
    "rents": "2",
    "guaranteed_payments": "10",
    "interest_income": "3",
    "dividends": "4",
    "capital_gain": "5",
    "other_income": "7",
    "salaries_wages": "9",
    "repairs_maintenance": "14",
    "bad_debts": "15",
    "rents_paid": "16",
    "taxes": "17",
    "interest_paid": "18",
    "depreciation": "19",
    "depletion": "20",
    "other_deductions": "21",
}

FORM_1120S_LINES = {
    "gross_receipts": "1a",
    "returns": "1b",
    "cost_of_goods": "2",
    "ordinary_income": "21",
    "interest_income": "3",
    "net_rental": "4",
    "capital_gain": "5",
    "compensation": "7",
    "salaries_wages": "8",
    "repairs": "9",
    "bad_debts": "10",
    "rents": "11",
    "taxes": "12",
    "interest": "13",
    "depreciation": "14",
    "depletion": "15",
    "other_deductions": "20",
}

FORM_8825_LINES = {
    "rents_received": "2",
    "advertising": "9",
    "auto": "10",
    "insurance": "11",
    "interest": "12",
    "legal": "13",
    "management_fees": "14",
    "mortgage": "15",
    "other_interest": "16",
    "repairs": "17",
    "supplies": "18",
    "taxes": "19",
    "utilities": "20",
    "wages": "21",
    "depreciation": "23",
    "other_expenses": "24",
}

FORM_4562_LINES = {
    "section_179_expense": "12",
    "bonus_depreciation": "14",
    "macrs_depreciation": "15",
    "ads_depreciation": "16",
    "listed_property": "25",
    "total_depreciation": "22",
}

SCHEDULE_E_LINES = {
    "rents_received": "3",
    "royalties": "4",
    "advertising": "5",
    "auto": "6",
    "cleaning": "7",
    "commissions": "8",
    "insurance": "9",
    "legal": "10",
    "management_fees": "11",
    "mortgage_interest": "12",
    "other_interest": "13",
    "repairs": "14",
    "supplies": "15",
    "taxes": "16",
    "utilities": "17",
    "depreciation": "18",
    "other_expenses": "19",
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


def _line_totals_for_form(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
    form_name: str,
) -> tuple[dict[str, Decimal], dict[str, Decimal], Decimal, Decimal]:
    """Return (line_income, line_expense, fallback_income, fallback_expense)."""
    txns = _txns_for_period(db, tenant_id, user_id, start_date, end_date)
    mappings = {
        m.coa_account_id: m for m in db.query(models.TaxLineMapping).filter(
            models.TaxLineMapping.tenant_id == tenant_id,
            models.TaxLineMapping.user_id == user_id,
            models.TaxLineMapping.form == form_name,
        ).all()
    }
    line_income: dict[str, Decimal] = {}
    line_expense: dict[str, Decimal] = {}
    fallback_income = Decimal("0")
    fallback_expense = Decimal("0")
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
            fallback_expense += exp
    return line_income, line_expense, fallback_income, fallback_expense


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
    line_income, line_expense, fallback_income, fallback_expenses = _line_totals_for_form(
        db, tenant_id, user_id, start_date, end_date, "Schedule C"
    )
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
        "fallback_income": float(fallback_income),
        "fallback_expenses": float(fallback_expenses),
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


def _form_summary(
    form_name: str,
    line_income: dict[str, Decimal],
    line_expense: dict[str, Decimal],
    fallback_income: Decimal,
    fallback_expense: Decimal,
    year: int,
) -> dict:
    """Build a generic form result dict."""
    total_income = sum(line_income.values(), Decimal("0")) + fallback_income
    total_expenses = sum(line_expense.values(), Decimal("0")) + fallback_expense
    return {
        "form": form_name,
        "year": year,
        "total_income": float(total_income),
        "total_expenses": float(total_expenses),
        "net_income": float(total_income - total_expenses),
        "lines": {
            "income": {k: float(v) for k, v in line_income.items()},
            "expense": {k: float(v) for k, v in line_expense.items()},
        },
        "fallback_income": float(fallback_income),
        "fallback_expenses": float(fallback_expense),
        "generated_at": date.today().isoformat(),
    }


def form_1065(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate Form 1065 partnership return summary."""
    line_income, line_expense, fallback_income, fallback_expense = _line_totals_for_form(
        db, tenant_id, user_id, start_date, end_date, "1065"
    )
    return _form_summary(
        "1065", line_income, line_expense,
        fallback_income, fallback_expense, start_date.year,
    )


def form_1120s(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate Form 1120-S S corporation return summary."""
    line_income, line_expense, fallback_income, fallback_expense = _line_totals_for_form(
        db, tenant_id, user_id, start_date, end_date, "1120-S"
    )
    return _form_summary(
        "1120-S", line_income, line_expense,
        fallback_income, fallback_expense, start_date.year,
    )


def form_8825(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate Form 8825 rental real estate income/loss summary."""
    line_income, line_expense, fallback_income, fallback_expense = _line_totals_for_form(
        db, tenant_id, user_id, start_date, end_date, "8825"
    )
    return _form_summary(
        "8825", line_income, line_expense,
        fallback_income, fallback_expense, start_date.year,
    )


def schedule_e(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate Schedule E supplemental rental/royalty income summary."""
    line_income, line_expense, fallback_income, fallback_expense = _line_totals_for_form(
        db, tenant_id, user_id, start_date, end_date, "Schedule E"
    )
    return _form_summary(
        "Schedule E", line_income, line_expense,
        fallback_income, fallback_expense, start_date.year,
    )


def form_4562(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
) -> dict:
    """Generate Form 4562 depreciation and amortization summary."""
    assets = db.query(models.DepreciationAsset).filter(
        models.DepreciationAsset.tenant_id == tenant_id,
        models.DepreciationAsset.user_id == user_id,
    ).all()
    lines: dict[str, Decimal] = {}
    total_section_179 = Decimal("0")
    total_bonus = Decimal("0")
    total_depreciation = Decimal("0")
    for asset in assets:
        schedule = compute_schedule(
            cost_basis=asset.cost_basis,
            placed_in_service_date=asset.placed_in_service_date,
            recovery_period_years=asset.recovery_period_years,
            method=asset.method,
            convention=asset.convention,
            section_179=asset.section_179,
            bonus_depreciation=asset.bonus_depreciation,
            salvage_value=asset.salvage_value,
        )
        for entry in schedule:
            if entry.year == year:
                total_section_179 += Decimal(str(entry.section_179 or 0))
                total_bonus += Decimal(str(entry.bonus or 0))
                total_depreciation += Decimal(str(entry.regular_depreciation or 0))
    lines[FORM_4562_LINES["section_179_expense"]] = total_section_179
    lines[FORM_4562_LINES["bonus_depreciation"]] = total_bonus
    lines[FORM_4562_LINES["macrs_depreciation"]] = total_depreciation
    lines[FORM_4562_LINES["total_depreciation"]] = total_section_179 + total_bonus + total_depreciation
    return {
        "form": "4562",
        "year": year,
        "lines": {k: float(v) for k, v in lines.items()},
        "total_depreciation": float(lines[FORM_4562_LINES["total_depreciation"]]),
        "generated_at": date.today().isoformat(),
    }


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


def form_1099_summary_csv(rows: list[dict]) -> str:
    """Render 1099 summary rows as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["payee", "form", "year", "amount"])
    for r in rows:
        writer.writerow([r["payee"], r["form"], r["year"], r["amount"]])
    return output.getvalue()


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
        "form_1099_csv": form_1099_summary_csv(form_1099s),
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


def json_dumps_compact(data: dict) -> str:
    """Return compact JSON with stable key order."""
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def csv_rows_to_csv(rows: list[dict]) -> str:
    """Convert a list of dicts to CSV."""
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()
