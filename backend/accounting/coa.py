"""Chart of Accounts domain logic for TaxFlow Pro v3.11.

The module reuses the existing ``GLAccount`` table (renamed conceptually to
coa_accounts in v3.11 docs) so v3.10 data remains intact.  Account types
follow the five-class bookkeeping model required by the unified register and
reports modules.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

if TYPE_CHECKING:
    from backend.models import GLAccount as COAAccountModel, User


class AccountType(enum.Enum):
    """Canonical five-class account type."""

    asset = "asset"
    liability = "liability"
    equity = "equity"
    income = "income"
    expense = "expense"


ACCOUNT_TYPE_ORDER = {
    AccountType.asset.value: 1,
    AccountType.liability.value: 2,
    AccountType.equity.value: 3,
    AccountType.income.value: 4,
    AccountType.expense.value: 5,
}


def _coa_account_to_dict(account: "COAAccountModel") -> dict:
    """Serialize a GLAccount row into the COA wire shape."""
    return {
        "id": account.id,
        "tenant_id": account.tenant_id,
        "user_id": account.user_id,
        "number": account.code,
        "name": account.name,
        "type": account.account_type,
        "parent_id": getattr(account, "parent_id", None),
        "is_active": getattr(account, "is_active", True),
        "balance": None,  # placeholder; populated by reporting/ledger later
        "created_at": account.created_at,
        "updated_at": getattr(account, "updated_at", None),
    }


def _set_coa_tenant(db: Session, tenant_id: int | None) -> None:
    """Apply PostgreSQL RLS tenant context for COA queries if needed."""
    if is_postgres() and tenant_id is not None:
        set_tenant_id(db, tenant_id)


def get_accounts(
    db: Session,
    tenant_id: int,
    user_id: int | None = None,
) -> list[dict]:
    """Return all COA accounts for a tenant ordered by type then code."""
    _set_coa_tenant(db, tenant_id)
    query = db.query(models.GLAccount).filter(models.GLAccount.tenant_id == tenant_id)
    if user_id is not None:
        query = query.filter(models.GLAccount.user_id == user_id)
    accounts = query.all()
    accounts.sort(key=lambda a: (ACCOUNT_TYPE_ORDER.get(a.account_type, 99), a.code))
    return [_coa_account_to_dict(a) for a in accounts]


def get_account(
    db: Session,
    account_id: int,
    tenant_id: int,
    user_id: int | None = None,
) -> dict | None:
    """Return a single COA account or None if not found / not owned."""
    _set_coa_tenant(db, tenant_id)
    query = db.query(models.GLAccount).filter(
        models.GLAccount.id == account_id,
        models.GLAccount.tenant_id == tenant_id,
    )
    if user_id is not None:
        query = query.filter(models.GLAccount.user_id == user_id)
    account = query.first()
    return _coa_account_to_dict(account) if account else None


def create_account(
    db: Session,
    tenant_id: int,
    user_id: int,
    code: str,
    name: str,
    account_type: str,
    parent_id: int | None = None,
    is_active: bool = True,
) -> dict:
    """Create a new COA account.

    Rejects duplicate account codes within the same tenant.
    """
    _set_coa_tenant(db, tenant_id)
    normalized_type = _normalize_account_type(account_type)

    existing = (
        db.query(models.GLAccount)
        .filter(
            models.GLAccount.tenant_id == tenant_id,
            func.lower(models.GLAccount.code) == code.lower().strip(),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Account code already exists")

    if parent_id is not None:
        parent = (
            db.query(models.GLAccount)
            .filter(
                models.GLAccount.id == parent_id,
                models.GLAccount.tenant_id == tenant_id,
            )
            .first()
        )
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent account not found")

    account = models.GLAccount(
        tenant_id=tenant_id,
        user_id=user_id,
        code=code.strip(),
        name=name.strip(),
        account_type=normalized_type,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _coa_account_to_dict(account)


def update_account(
    db: Session,
    account_id: int,
    tenant_id: int,
    user_id: int,
    code: str | None = None,
    name: str | None = None,
    account_type: str | None = None,
    parent_id: int | None = None,
    is_active: bool | None = None,
) -> dict:
    """Update an existing COA account."""
    _set_coa_tenant(db, tenant_id)
    account = (
        db.query(models.GLAccount)
        .filter(
            models.GLAccount.id == account_id,
            models.GLAccount.tenant_id == tenant_id,
            models.GLAccount.user_id == user_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if code is not None:
        new_code = code.strip().lower()
        duplicate = (
            db.query(models.GLAccount)
            .filter(
                models.GLAccount.tenant_id == tenant_id,
                models.GLAccount.id != account_id,
                func.lower(models.GLAccount.code) == new_code,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Account code already exists")
        account.code = code.strip()

    if name is not None:
        account.name = name.strip()

    if account_type is not None:
        account.account_type = _normalize_account_type(account_type)

    if parent_id is not None:
        parent = (
            db.query(models.GLAccount)
            .filter(
                models.GLAccount.id == parent_id,
                models.GLAccount.tenant_id == tenant_id,
            )
            .first()
        )
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent account not found")
        # Prevent creating a cycle by assigning self as parent.
        if parent.id == account.id:
            raise HTTPException(status_code=400, detail="Account cannot be its own parent")

    if is_active is not None:
        account.is_active = is_active

    db.commit()
    db.refresh(account)
    return _coa_account_to_dict(account)


def delete_account(
    db: Session,
    account_id: int,
    tenant_id: int,
    user_id: int,
) -> None:
    """Delete a COA account.

    Guard: accounts referenced by transactions, general ledger entries, or
    categorization rules cannot be removed until those references are cleared.
    """
    _set_coa_tenant(db, tenant_id)
    account = (
        db.query(models.GLAccount)
        .filter(
            models.GLAccount.id == account_id,
            models.GLAccount.tenant_id == tenant_id,
            models.GLAccount.user_id == user_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    in_use = (
        db.query(models.Transaction)
        .filter(models.Transaction.gl_account_id == account_id)
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Account is referenced by transactions and cannot be deleted",
        )

    in_use = (
        db.query(models.GeneralLedgerEntry)
        .filter(
            (models.GeneralLedgerEntry.debit_account_id == account_id)
            | (models.GeneralLedgerEntry.credit_account_id == account_id)
        )
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Account is referenced by general ledger entries and cannot be deleted",
        )

    in_use = (
        db.query(models.CategorizationRule)
        .filter(models.CategorizationRule.gl_account_id == account_id)
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Account is referenced by categorization rules and cannot be deleted",
        )

    db.delete(account)
    db.commit()


def _normalize_account_type(value: str) -> str:
    """Validate and normalize an account type string."""
    lowered = value.lower().strip()
    allowed = {m.value for m in AccountType}
    if lowered not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid account type '{value}'. Must be one of: {', '.join(sorted(allowed))}",
        )
    return lowered
