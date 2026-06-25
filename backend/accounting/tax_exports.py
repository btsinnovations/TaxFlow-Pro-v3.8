"""Tax filing export domain logic for TaxFlow Pro v3.11."""
from __future__ import annotations

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


def schedule_c(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate a Schedule C-style summary for the period."""
    txns = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == user_id,
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
    ).all()
    income = Decimal("0")
    expenses = Decimal("0")
    for t in txns:
        amt = Decimal(str(t.amount or 0))
        if t.tx_type and t.tx_type.lower() in ("credit", "deposit", "income"):
            income += amt
        else:
            expenses += amt
    return {
        "form": "Schedule C",
        "year": start_date.year,
        "line_1_gross_receipts": float(income),
        "line_28_total_expenses": float(expenses),
        "line_31_net_profit": float(income - expenses),
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


def list_mappings(db: Session, tenant_id: int, user_id: int) -> list[models.TaxLineMapping]:
    return db.query(models.TaxLineMapping).filter(
        models.TaxLineMapping.tenant_id == tenant_id,
        models.TaxLineMapping.user_id == user_id,
    ).order_by(models.TaxLineMapping.form, models.TaxLineMapping.line).all()
