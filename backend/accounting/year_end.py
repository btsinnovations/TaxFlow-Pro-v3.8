"""Year-end closing and tax-package generation for TaxFlow Pro v3.11.6."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.accounting.reports import balance_sheet, profit_and_loss, trial_balance
from backend.accounting.tax_exports import (
    csv_rows_to_csv,
    form_1065,
    form_1099_nec_misc,
    form_1099_summary_csv,
    form_1120s,
    form_4562,
    form_8825,
    json_dumps_compact,
    schedule_c,
    schedule_c_csv,
    schedule_e,
)


RETAINED_EARNINGS_NUMBER = 3100
INCOME_SUMMARY_NUMBER = 3999


def _get_or_create_coa(
    db: Session,
    tenant_id: int,
    number: int,
    name: str,
    account_type: str,
) -> models.CoaAccount:
    existing = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.tenant_id == tenant_id,
            models.CoaAccount.number == number,
        )
        .first()
    )
    if existing:
        return existing
    account = models.CoaAccount(
        tenant_id=tenant_id,
        number=number,
        name=name,
        type=account_type,
    )
    db.add(account)
    db.flush()
    return account


def _coa_balance(
    db: Session,
    account_id: int,
    start_date: date,
    end_date: date,
) -> Decimal:
    """Return signed balance for an account in the period.

    Uses the same sign convention as profit_and_loss: credits positive for
    income, debits positive for expenses.
    """
    total = Decimal("0")
    for t in (
        db.query(models.Transaction)
        .filter(
            models.Transaction.coa_account_id == account_id,
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
        )
        .all()
    ):
        tx_type = (t.tx_type or "").lower()
        amt = Decimal(str(t.amount or 0))
        if tx_type in ("credit", "deposit", "income"):
            total += amt
        else:
            total -= amt
    return total


def close_year(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
) -> dict:
    """Run a simplified year-end close for the tenant.

    Creates closing GL entries that zero out income and expense COA accounts
    for the year and move the net result into Retained Earnings. Also marks
    every period that falls within the year as closed.
    """
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    retained_earnings = _get_or_create_coa(
        db, tenant_id, RETAINED_EARNINGS_NUMBER, "Retained Earnings", "equity"
    )
    income_summary = _get_or_create_coa(
        db, tenant_id, INCOME_SUMMARY_NUMBER, "Income Summary", "equity"
    )

    accounts = (
        db.query(models.CoaAccount)
        .filter(models.CoaAccount.tenant_id == tenant_id)
        .all()
    )

    net_income = Decimal("0")
    entries_created = 0

    for a in accounts:
        if a.type != "income":
            continue
        balance = _coa_balance(db, a.id, start, end)
        if balance == 0:
            continue
        db.add(
            models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=end,
                description=f"Close {a.name} for {year}",
                debit_coa_account_id=a.id,
                credit_coa_account_id=income_summary.id,
                amount=balance,
                memo=f"Year-end close {year}",
                entry_type="adjusting",
            )
        )
        entries_created += 1
        net_income += balance

    for a in accounts:
        if a.type != "expense":
            continue
        balance = _coa_balance(db, a.id, start, end)
        if balance == 0:
            continue
        db.add(
            models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=end,
                description=f"Close {a.name} for {year}",
                debit_coa_account_id=income_summary.id,
                credit_coa_account_id=a.id,
                amount=-balance,
                memo=f"Year-end close {year}",
                entry_type="adjusting",
            )
        )
        entries_created += 1
        net_income += balance

    summary_balance = net_income

    if summary_balance != 0:
        if summary_balance > 0:
            debit_acct = income_summary
            credit_acct = retained_earnings
        else:
            debit_acct = retained_earnings
            credit_acct = income_summary
        db.add(
            models.GeneralLedgerEntry(
                tenant_id=tenant_id,
                user_id=user_id,
                date=end,
                description=f"Close Income Summary to Retained Earnings for {year}",
                debit_coa_account_id=debit_acct.id,
                credit_coa_account_id=credit_acct.id,
                amount=abs(summary_balance),
                memo=f"Year-end close {year}",
                entry_type="adjusting",
            )
        )
        entries_created += 1

    periods = (
        db.query(models.Period)
        .filter(
            models.Period.tenant_id == tenant_id,
            models.Period.start_date >= start,
            models.Period.end_date <= end,
        )
        .all()
    )
    closed_periods = 0
    for p in periods:
        if not p.is_closed:
            p.is_closed = True
            p.closed_at = datetime.now(timezone.utc)
            closed_periods += 1

    db.commit()

    return {
        "year": year,
        "entries_created": entries_created,
        "closed_periods": closed_periods,
        "net_income": float(summary_balance),
    }


def _general_ledger_csv(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date,
) -> str:
    entries = (
        db.query(models.GeneralLedgerEntry)
        .filter(
            models.GeneralLedgerEntry.tenant_id == tenant_id,
            models.GeneralLedgerEntry.date >= start_date,
            models.GeneralLedgerEntry.date <= end_date,
        )
        .order_by(models.GeneralLedgerEntry.date, models.GeneralLedgerEntry.id)
        .all()
    )
    rows = [
        {
            "id": e.id,
            "date": e.date.isoformat(),
            "description": e.description,
            "debit_account_id": e.debit_account_id,
            "credit_account_id": e.credit_account_id,
            "debit_coa_account_id": e.debit_coa_account_id,
            "credit_coa_account_id": e.credit_coa_account_id,
            "amount": float(e.amount),
            "memo": e.memo,
            "entry_type": e.entry_type,
            "workpaper_ref": e.workpaper_ref,
        }
        for e in entries
    ]
    return csv_rows_to_csv(rows)


def _review_flags_json(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date,
) -> str:
    flags = (
        db.query(models.Flag)
        .filter(
            models.Flag.tenant_id == tenant_id,
        )
        .all()
    )
    data = {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "total": len(flags),
        "unresolved": sum(1 for f in flags if not f.resolved),
        "flags": [
            {
                "id": f.id,
                "note": f.note,
                "resolved": f.resolved,
                "created_by": f.created_by,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
            }
            for f in flags
        ],
    }
    return json_dumps_compact(data)


def generate_year_end_package(
    db: Session,
    tenant_id: int,
    user_id: int,
    year: int,
) -> bytes:
    """Generate a zip archive containing the year-end package files."""
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    pnl = profit_and_loss(db, tenant_id, user_id, start, end)
    tb = trial_balance(db, tenant_id, user_id, end)
    bs = balance_sheet(db, tenant_id, user_id, end)
    schedule_c_result = schedule_c(db, tenant_id, user_id, start, end)
    f1065 = form_1065(db, tenant_id, user_id, start, end)
    f1120s = form_1120s(db, tenant_id, user_id, start, end)
    f8825 = form_8825(db, tenant_id, user_id, start, end)
    f4562 = form_4562(db, tenant_id, user_id, year)
    schedule_e_result = schedule_e(db, tenant_id, user_id, start, end)
    form_1099s = form_1099_nec_misc(db, tenant_id, user_id, year)

    gl_csv = _general_ledger_csv(db, tenant_id, start, end)
    review_flags = _review_flags_json(db, tenant_id, start, end)

    index = {
        "year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"name": "trial_balance.csv", "type": "csv"},
            {"name": "income_statement.csv", "type": "csv"},
            {"name": "balance_sheet.json", "type": "json"},
            {"name": "general_ledger.csv", "type": "csv"},
            {"name": "schedule_c.json", "type": "json"},
            {"name": "form_1065.json", "type": "json"},
            {"name": "form_1120s.json", "type": "json"},
            {"name": "form_8825.json", "type": "json"},
            {"name": "form_4562.json", "type": "json"},
            {"name": "schedule_e.json", "type": "json"},
            {"name": "form_1099_summary.csv", "type": "csv"},
            {"name": "review_flags.json", "type": "json"},
        ],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("trial_balance.csv", csv_rows_to_csv(tb))
        zf.writestr("income_statement.csv", csv_rows_to_csv(pnl["by_account"]))
        zf.writestr("balance_sheet.json", json_dumps_compact(bs))
        zf.writestr("general_ledger.csv", gl_csv)
        zf.writestr("schedule_c.json", json_dumps_compact(schedule_c_result))
        zf.writestr("schedule_c.csv", schedule_c_csv(schedule_c_result))
        zf.writestr("form_1065.json", json_dumps_compact(f1065))
        zf.writestr("form_1120s.json", json_dumps_compact(f1120s))
        zf.writestr("form_8825.json", json_dumps_compact(f8825))
        zf.writestr("form_4562.json", json_dumps_compact(f4562))
        zf.writestr("schedule_e.json", json_dumps_compact(schedule_e_result))
        zf.writestr("form_1099_summary.csv", form_1099_summary_csv(form_1099s))
        zf.writestr("review_flags.json", review_flags)
        zf.writestr("workpaper_index.json", json_dumps_compact(index))

    buf.seek(0)
    return buf.read()
