"""Financial reports domain logic for TaxFlow Pro v3.11.6."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


def _coa_type_order(account_type: str) -> int:
    order = {"asset": 1, "liability": 2, "equity": 3, "income": 4, "expense": 5}
    return order.get(account_type.lower(), 99)


def _txn_amount_by_type(txn: models.Transaction) -> tuple[Decimal, Decimal]:
    """Return (income_amount, expense_amount) based on tx_type.

    Backward-compatible interpretation used by P&L and early trial balance.
    """
    amt = Decimal(str(txn.amount or 0))
    tx_type = (txn.tx_type or "").lower()
    if tx_type in ("credit", "deposit", "income"):
        return (amt, Decimal("0"))
    return (Decimal("0"), amt)


def _txn_amount_signed_for_account(
    txn: models.Transaction,
    account_type: str,
) -> Decimal:
    """Return signed amount based on account normal balance.

    Asset and expense accounts normally increase with debits (positive).
    Liability, equity, and income accounts normally increase with credits
    (positive). Debit-type txns are recorded as negative for the latter.
    """
    amt = Decimal(str(txn.amount or 0))
    tx_type = (txn.tx_type or "").lower()
    is_credit = tx_type in ("credit", "deposit", "income")
    if account_type.lower() in ("asset", "expense"):
        return amt if not is_credit else -amt
    return amt if is_credit else -amt


def _txns_for_account(
    db: Session,
    account_id: int,
    start_date: Optional[date],
    end_date: Optional[date],
) -> list[models.Transaction]:
    query = db.query(models.Transaction).filter(
        models.Transaction.coa_account_id == account_id,
    )
    if start_date is not None:
        query = query.filter(models.Transaction.date >= start_date)
    if end_date is not None:
        query = query.filter(models.Transaction.date <= end_date)
    return query.all()


def _coa_accounts_for_tenant(db: Session, tenant_id: int) -> list[models.CoaAccount]:
    return db.query(models.CoaAccount).filter(
        models.CoaAccount.tenant_id == tenant_id,
    ).order_by(models.CoaAccount.number).all()


def _build_coa_tree(
    accounts: list[models.CoaAccount],
    balances: dict[int, Decimal],
) -> list[dict]:
    """Build a hierarchy of COA accounts with rolled-up balances."""
    account_map = {a.id: a for a in accounts}
    children_map: dict[int, list[int]] = {}
    for a in accounts:
        children_map.setdefault(a.parent_id, []).append(a.id)

    def _rollup(account_id: int) -> Decimal:
        direct = balances.get(account_id, Decimal("0"))
        child_total = Decimal("0")
        for child_id in children_map.get(account_id, []):
            child_total += _rollup(child_id)
        total = direct + child_total
        balances[account_id] = total
        return total

    for root_id in children_map.get(None, []):
        _rollup(root_id)

    def _serialize(account_id: int) -> dict:
        a = account_map[account_id]
        return {
            "id": a.id,
            "number": str(a.number),
            "name": a.name,
            "type": a.type,
            "balance": float(balances.get(account_id, Decimal("0"))),
            "children": [_serialize(cid) for cid in children_map.get(account_id, [])],
        }

    return [_serialize(root_id) for root_id in children_map.get(None, [])]


def profit_and_loss(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Return a P&L by COA account type for the date range.

    Transactions without a COA assignment are bucketed into an
    "Uncategorized" income/expense pseudo-account for backward compatibility.
    """
    accounts = _coa_accounts_for_tenant(db, tenant_id)
    income = Decimal("0")
    expenses = Decimal("0")
    by_account: dict[int, dict] = {}

    # COA-mapped transactions
    for a in accounts:
        if a.type not in ("income", "expense"):
            continue
        inc = Decimal("0")
        exp = Decimal("0")
        for t in _txns_for_account(db, a.id, start_date, end_date):
            i, e = _txn_amount_by_type(t)
            inc += i
            exp += e
        if a.type == "income":
            amount = inc
            income += inc
        else:
            amount = exp
            expenses += exp
        by_account[a.id] = {
            "id": a.id,
            "number": str(a.number),
            "name": a.name,
            "type": a.type,
            "amount": float(amount),
        }

    # Uncategorized transactions (no COA mapping)
    uncategorized_income = Decimal("0")
    uncategorized_expenses = Decimal("0")
    for t in _uncategorized_txns(db, tenant_id, start_date, end_date):
        i, e = _txn_amount_by_type(t)
        uncategorized_income += i
        uncategorized_expenses += e
    income += uncategorized_income
    expenses += uncategorized_expenses
    if uncategorized_income != 0 or uncategorized_expenses != 0:
        by_account[0] = {
            "id": 0,
            "number": "0000",
            "name": "Uncategorized",
            "type": "expense" if uncategorized_expenses >= uncategorized_income else "income",
            "amount": float(
                uncategorized_income if uncategorized_income >= uncategorized_expenses else uncategorized_expenses
            ),
        }

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "income": float(income),
        "expenses": float(expenses),
        "net": float(income - expenses),
        "by_account": list(by_account.values()),
    }


def _uncategorized_txns(
    db: Session,
    tenant_id: int,
    start_date: date,
    end_date: date,
) -> list[models.Transaction]:
    return db.query(models.Transaction).filter(
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.coa_account_id.is_(None),
        models.Transaction.gl_account_id.is_(None),
        models.Transaction.date >= start_date,
        models.Transaction.date <= end_date,
    ).all()


def trial_balance(
    db: Session,
    tenant_id: int,
    user_id: int,
    as_of: date,
) -> list[dict]:
    """Return trial balance rows grouped by COA account."""
    accounts = _coa_accounts_for_tenant(db, tenant_id)
    rows = []
    for a in accounts:
        debit = Decimal("0")
        credit = Decimal("0")
        for t in _txns_for_account(db, a.id, None, as_of):
            tx_type = (t.tx_type or "").lower()
            amt = Decimal(str(t.amount or 0))
            if tx_type in ("debit", "expense", "check"):
                debit += amt
            else:
                credit += amt
        rows.append({
            "account_id": a.id,
            "code": str(a.number),
            "name": a.name,
            "type": a.type,
            "debit": float(debit),
            "credit": float(credit),
            "net": float(credit - debit),
        })
    rows.sort(key=lambda r: (_coa_type_order(r["type"]), r["code"]))
    return rows


def balance_sheet(
    db: Session,
    tenant_id: int,
    user_id: int,
    as_of: date,
) -> dict:
    """Return a balance sheet as of a date, grouped by COA type."""
    accounts = _coa_accounts_for_tenant(db, tenant_id)
    balances: dict[int, Decimal] = {}
    sections: dict[str, Decimal] = {
        "asset": Decimal("0"),
        "liability": Decimal("0"),
        "equity": Decimal("0"),
    }
    for a in accounts:
        if a.type not in sections:
            continue
        balance = Decimal("0")
        for t in _txns_for_account(db, a.id, None, as_of):
            balance += _txn_amount_signed_for_account(t, a.type)
        balances[a.id] = balance
        sections[a.type] += balance

    tree = _build_coa_tree(accounts, balances)
    total_assets = sections["asset"]
    total_liabilities = sections["liability"]
    total_equity = sections["equity"]
    return {
        "as_of": as_of.isoformat(),
        "sections": {
            "assets": {
                "total": float(total_assets),
                "accounts": [n for n in tree if n["type"] == "asset"],
            },
            "liabilities": {
                "total": float(total_liabilities),
                "accounts": [n for n in tree if n["type"] == "liability"],
            },
            "equity": {
                "total": float(total_equity),
                "accounts": [n for n in tree if n["type"] == "equity"],
            },
        },
        "total_assets": float(total_assets),
        "total_liabilities": float(total_liabilities),
        "total_equity": float(total_equity),
        "liabilities_plus_equity": float(total_liabilities + total_equity),
    }


def cash_flow_statement(
    db: Session,
    tenant_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Return a simplified cash flow statement for the period.

    Operating cash flow is approximated as income minus expenses (accrual
    proxy). Investing reflects non-cash asset account changes and financing
    reflects liability/equity changes. This is intentionally simplified for
    the Track 6 Reports Center milestone.
    """
    accounts = _coa_accounts_for_tenant(db, tenant_id)

    operating = Decimal("0")
    investing = Decimal("0")
    financing = Decimal("0")
    detail: dict[str, list[dict]] = {"operating": [], "investing": [], "financing": []}

    for a in accounts:
        balance = Decimal("0")
        for t in _txns_for_account(db, a.id, start_date, end_date):
            balance += _txn_amount_signed_for_account(t, a.type)
        if balance == 0:
            continue
        if a.type == "income":
            operating += balance
            bucket = "operating"
        elif a.type == "expense":
            operating -= balance
            bucket = "operating"
        elif a.type == "asset":
            investing += balance
            bucket = "investing"
        elif a.type == "liability":
            financing += balance
            bucket = "financing"
        elif a.type == "equity":
            financing += balance
            bucket = "financing"
        else:
            continue
        detail[bucket].append({
            "id": a.id,
            "number": str(a.number),
            "name": a.name,
            "amount": float(balance if a.type != "expense" else -balance),
        })

    net_cash = operating + investing + financing
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "operating": float(operating),
        "investing": float(investing),
        "financing": float(financing),
        "net_change": float(net_cash),
        "detail": detail,
    }
