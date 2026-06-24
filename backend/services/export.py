"""CSV export services for TaxFlow Pro v3.9.

All functions return a CSV string. Routers are responsible for wrapping the
result in a FastAPI Response with `text/csv` media type.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from .. import models
from ..utils.redaction import mask_account_number, mask_transaction_description


def _mask_text_fields(rows: list, header: list) -> list:
    """Mask PII in CSV rows by header name heuristics.

    Columns containing 'account', 'card', 'routing', 'tax_id' are masked to last 4.
    Columns named 'description' or 'memo' have long digit runs scrubbed.
    """
    if not rows:
        return rows
    masked = [header]
    lower_header = [h.lower().replace(" ", "_") for h in header]
    for row in rows[1:]:
        new_row = []
        for col_idx, value in enumerate(row):
            key = lower_header[col_idx]
            if value is None:
                new_row.append("")
            elif any(part in key for part in ("account", "card", "routing", "tax_id")):
                new_row.append(mask_account_number(str(value)) or "")
            elif "description" in key or "memo" in key:
                new_row.append(mask_transaction_description(str(value)) or "")
            else:
                new_row.append(str(value))
        masked.append(new_row)
    return masked


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _csv_string(rows: List[List[str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _date_in_range(value: Optional[date], start: Optional[str], end: Optional[str]) -> bool:
    if value is None:
        return False
    if start:
        start_dt = _to_date(start)
        if start_dt and value < start_dt:
            return False
    if end:
        end_dt = _to_date(end)
        if end_dt and value > end_dt:
            return False
    return True


def export_transactions(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    query = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == user_id,
    ).order_by(models.Transaction.date.asc())
    header = ["id", "date", "description", "amount", "type", "category", "workpaper_ref", "gl_account_id"]
    rows = [header]
    for tx in query.all():
        if _date_in_range(tx.date, start_date, end_date):
            tx_date = tx.date.isoformat() if tx.date else ""
            rows.append([
                str(tx.id), tx_date, tx.description or "",
                f"{_to_float(tx.amount)}", tx.tx_type or "", tx.category or "",
                tx.workpaper_ref or "", str(tx.gl_account_id) if tx.gl_account_id else "",
            ])
    return _csv_string(_mask_text_fields(rows, header))


def export_general_ledger(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    query = db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.user_id == user_id,
    ).order_by(models.GeneralLedgerEntry.date.asc())
    header = ["id", "date", "description", "debit_account_id", "credit_account_id", "amount", "memo", "workpaper_ref"]
    rows = [header]
    for entry in query.all():
        if _date_in_range(entry.date, start_date, end_date):
            entry_date = entry.date.isoformat() if entry.date else ""
            rows.append([
                str(entry.id), entry_date, entry.description or "",
                str(entry.debit_account_id) if entry.debit_account_id else "",
                str(entry.credit_account_id) if entry.credit_account_id else "",
                f"{_to_float(entry.amount)}", entry.memo or "", entry.workpaper_ref or "",
            ])
    return _csv_string(_mask_text_fields(rows, header))


def export_trial_balance(
    db: Session,
    tenant_id: int,
    user_id: int,
    as_of_date: Optional[str] = None,
) -> str:
    """Return debits/credits per GL account up to as_of_date (inclusive)."""
    accounts = db.query(models.GLAccount).filter(
        models.GLAccount.tenant_id == tenant_id,
        models.GLAccount.user_id == user_id,
    ).all()
    account_map = {a.id: a for a in accounts}

    balances: dict[int, Decimal] = {a.id: Decimal("0.00") for a in accounts}
    for entry in db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.user_id == user_id,
    ).all():
        entry_date = _to_date(entry.date)
        if as_of_date and entry_date and entry_date > _to_date(as_of_date):
            continue
        amount = entry.amount or Decimal("0.00")
        if entry.debit_account_id:
            balances[entry.debit_account_id] += amount
        if entry.credit_account_id:
            balances[entry.credit_account_id] -= amount

    rows = [["account_id", "code", "name", "account_type", "balance"]]
    for account_id, bal in sorted(balances.items(), key=lambda x: x[0]):
        account = account_map.get(account_id)
        rows.append([
            str(account_id), account.code if account else "", account.name if account else "",
            account.account_type if account else "", f"{float(bal):.2f}",
        ])
    return _csv_string(rows)


def export_profit_loss(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: str,
    end_date: str,
) -> str:
    """Aggregate income and expense GL account balances for the period."""
    accounts = db.query(models.GLAccount).filter(
        models.GLAccount.tenant_id == tenant_id,
        models.GLAccount.user_id == user_id,
        models.GLAccount.account_type.in_(["income", "expense"]),
    ).all()
    account_map = {a.id: a for a in accounts}
    balances: dict[int, Decimal] = {a.id: Decimal("0.00") for a in accounts}

    for entry in db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.user_id == user_id,
    ).all():
        if not _date_in_range(entry.date, start_date, end_date):
            continue
        amount = entry.amount or Decimal("0.00")
        if entry.debit_account_id in balances:
            balances[entry.debit_account_id] += amount
        if entry.credit_account_id in balances:
            balances[entry.credit_account_id] -= amount

    total_income = Decimal("0.00")
    total_expense = Decimal("0.00")
    detail_rows: List[List[str]] = []
    for account_id, bal in sorted(balances.items(), key=lambda x: x[0]):
        account = account_map[account_id]
        detail_rows.append([
            str(account_id), account.code, account.name, account.account_type, f"{float(bal):.2f}",
        ])
        if account.account_type == "income":
            total_income += bal
        elif account.account_type == "expense":
            total_expense += bal

    rows = [
        ["account_id", "code", "name", "account_type", "amount"],
        *detail_rows,
        [],
        ["", "", "Total Income", "", f"{float(total_income):.2f}"],
        ["", "", "Total Expense", "", f"{float(total_expense):.2f}"],
        ["", "", "Net Income", "", f"{float(total_income - total_expense):.2f}"],
    ]
    return _csv_string(rows)


def export_balance_sheet(
    db: Session,
    tenant_id: int,
    user_id: int,
    as_of_date: str,
) -> str:
    """Aggregate asset, liability, and equity GL account balances as of date."""
    accounts = db.query(models.GLAccount).filter(
        models.GLAccount.tenant_id == tenant_id,
        models.GLAccount.user_id == user_id,
        models.GLAccount.account_type.in_(["asset", "liability", "equity"]),
    ).all()
    account_map = {a.id: a for a in accounts}
    balances: dict[int, Decimal] = {a.id: Decimal("0.00") for a in accounts}

    for entry in db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == tenant_id,
        models.GeneralLedgerEntry.user_id == user_id,
    ).all():
        entry_date = _to_date(entry.date)
        if entry_date and entry_date > _to_date(as_of_date):
            continue
        amount = entry.amount or Decimal("0.00")
        if entry.debit_account_id in balances:
            balances[entry.debit_account_id] += amount
        if entry.credit_account_id in balances:
            balances[entry.credit_account_id] -= amount

    totals: dict[str, Decimal] = {"asset": Decimal("0.00"), "liability": Decimal("0.00"), "equity": Decimal("0.00")}
    detail_rows: List[List[str]] = []
    for account_id, bal in sorted(balances.items(), key=lambda x: x[0]):
        account = account_map[account_id]
        detail_rows.append([
            str(account_id), account.code, account.name, account.account_type, f"{float(bal):.2f}",
        ])
        totals[account.account_type] += bal

    rows = [
        ["account_id", "code", "name", "account_type", "balance"],
        *detail_rows,
        [],
        ["", "", "Total Assets", "", f"{float(totals['asset']):.2f}"],
        ["", "", "Total Liabilities", "", f"{float(totals['liability']):.2f}"],
        ["", "", "Total Equity", "", f"{float(totals['equity']):.2f}"],
        ["", "", "Liabilities + Equity", "", f"{float(totals['liability'] + totals['equity']):.2f}"],
    ]
    return _csv_string(rows)
