"""Chart of Accounts domain logic for TaxFlow Pro v3.11.6.

Provides hierarchical COA CRUD with tenant scoping, standard COA seeding,
transaction-referenced deletion guards, renumbering, and parent reassignment.

The v3.11.6 migration introduces a dedicated ``coa_accounts`` table with
integer account numbers and self-referential parent_id for hierarchy.
The legacy ``GLAccount`` table remains for backward compatibility with
modules that have not yet been migrated (general ledger entries, etc.).
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
    from backend.models import CoaAccount, GLAccount, User


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


# Locked numbering scheme for COA accounts.
NUMBERING_RANGES = {
    "asset": (1000, 1999),
    "liability": (2000, 2999),
    "equity": (3000, 3999),
    "income": (4000, 4999),
    "expense": (5000, 9999),
}


# Standard small-business COA template for seeding new profiles.
STANDARD_COA = [
    # Assets (1000-1999)
    (1010, "Cash on Hand", "asset", None),
    (1020, "Operating Checking", "asset", None),
    (1030, "Savings Account", "asset", None),
    (1100, "Accounts Receivable", "asset", None),
    (1200, "Inventory", "asset", None),
    (1500, "Equipment", "asset", None),
    (1510, "Accumulated Depreciation - Equipment", "asset", None),
    (1600, "Furniture & Fixtures", "asset", None),
    (1610, "Accumulated Depreciation - F&F", "asset", None),
    # Liabilities (2000-2999)
    (2010, "Accounts Payable", "liability", None),
    (2020, "Credit Card Payable", "liability", None),
    (2100, "Accrued Liabilities", "liability", None),
    (2300, "Notes Payable", "liability", None),
    # Equity (3000-3999)
    (3010, "Owner's Capital", "equity", None),
    (3020, "Owner's Draw", "equity", None),
    (3100, "Retained Earnings", "equity", None),
    # Income (4000-4999)
    (4010, "Sales Revenue", "income", None),
    (4020, "Service Revenue", "income", None),
    (4030, "Interest Income", "income", None),
    # Expenses (5000-9999)
    (5010, "Cost of Goods Sold", "expense", None),
    (5100, "Rent Expense", "expense", None),
    (5110, "Utilities Expense", "expense", None),
    (5120, "Office Supplies", "expense", None),
    (5130, "Payroll Expense", "expense", None),
    (5140, "Payroll Tax Expense", "expense", None),
    (5150, "Insurance Expense", "expense", None),
    (5160, "Advertising & Marketing", "expense", None),
    (5170, "Travel Expense", "expense", None),
    (5180, "Meals & Entertainment", "expense", None),
    (5200, "Depreciation Expense", "expense", None),
    (5300, "Professional Fees", "expense", None),
    (5400, "Bank Fees", "expense", None),
    (5500, "Repairs & Maintenance", "expense", None),
    (5900, "Miscellaneous Expense", "expense", None),
]


def _coa_account_to_dict(account: "CoaAccount") -> dict:
    """Serialize a CoaAccount row into the COA wire shape."""
    return {
        "id": account.id,
        "tenant_id": account.tenant_id,
        "number": str(account.number),
        "name": account.name,
        "type": account.type,
        "parent_id": account.parent_id,
        "is_active": account.is_active,
        "balance": None,  # computed lazily by reporting/ledger queries when needed
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
    """Return all COA accounts for a tenant ordered by type then number."""
    _set_coa_tenant(db, tenant_id)
    query = db.query(models.CoaAccount).filter(models.CoaAccount.tenant_id == tenant_id)
    accounts = query.all()
    accounts.sort(key=lambda a: (ACCOUNT_TYPE_ORDER.get(a.type, 99), a.number))
    return [_coa_account_to_dict(a) for a in accounts]


def get_account(
    db: Session,
    account_id: int,
    tenant_id: int,
    user_id: int | None = None,
) -> dict | None:
    """Return a single COA account or None if not found / not owned."""
    _set_coa_tenant(db, tenant_id)
    query = db.query(models.CoaAccount).filter(
        models.CoaAccount.id == account_id,
        models.CoaAccount.tenant_id == tenant_id,
    )
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

    Rejects duplicate account numbers within the same tenant.
    The ``code`` parameter is accepted as a string for API compatibility
    but is stored as an integer in the ``number`` column.
    """
    _set_coa_tenant(db, tenant_id)
    normalized_type = _normalize_account_type(account_type)

    # Convert code to integer number
    try:
        number = int(str(code).strip())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Account number must be an integer, got '{code}'",
        )

    # Validate number is within the correct range for its type
    range_min, range_max = NUMBERING_RANGES.get(normalized_type, (5000, 9999))
    if not (range_min <= number <= range_max):
        raise HTTPException(
            status_code=422,
            detail=f"Account number {number} is outside the {normalized_type} range ({range_min}-{range_max})",
        )

    existing = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.tenant_id == tenant_id,
            models.CoaAccount.number == number,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Account code already exists")

    if parent_id is not None:
        parent = (
            db.query(models.CoaAccount)
            .filter(
                models.CoaAccount.id == parent_id,
                models.CoaAccount.tenant_id == tenant_id,
            )
            .first()
        )
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent account not found")

    account = models.CoaAccount(
        tenant_id=tenant_id,
        number=number,
        name=name.strip(),
        type=normalized_type,
        parent_id=parent_id,
        is_active=is_active,
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
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.id == account_id,
            models.CoaAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if code is not None:
        try:
            new_number = int(str(code).strip())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Account number must be an integer, got '{code}'",
            )

        duplicate = (
            db.query(models.CoaAccount)
            .filter(
                models.CoaAccount.tenant_id == tenant_id,
                models.CoaAccount.id != account_id,
                models.CoaAccount.number == new_number,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Account code already exists")
        account.number = new_number

    if name is not None:
        account.name = name.strip()

    if account_type is not None:
        account.type = _normalize_account_type(account_type)

    if parent_id is not None:
        if parent_id == 0:
            # 0 means "clear parent" — set to NULL
            account.parent_id = None
        else:
            parent = (
                db.query(models.CoaAccount)
                .filter(
                    models.CoaAccount.id == parent_id,
                    models.CoaAccount.tenant_id == tenant_id,
                )
                .first()
            )
            if parent is None:
                raise HTTPException(status_code=400, detail="Parent account not found")
            if parent.id == account.id:
                raise HTTPException(status_code=400, detail="Account cannot be its own parent")
            account.parent_id = parent_id

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
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.id == account_id,
            models.CoaAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    # Check coa_account_id references on transactions
    in_use = (
        db.query(models.Transaction)
        .filter(models.Transaction.coa_account_id == account_id)
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Account is referenced by transactions and cannot be deleted",
        )

    # Check coa_account_id references on general ledger entries
    in_use = (
        db.query(models.GeneralLedgerEntry)
        .filter(
            (models.GeneralLedgerEntry.debit_coa_account_id == account_id)
            | (models.GeneralLedgerEntry.credit_coa_account_id == account_id)
        )
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Account is referenced by general ledger entries and cannot be deleted",
        )

    # Check coa_account_id references on categorization rules
    in_use = (
        db.query(models.CategorizationRule)
        .filter(models.CategorizationRule.coa_account_id == account_id)
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="Account is referenced by categorization rules and cannot be deleted",
        )

    # Check for child accounts
    has_children = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.parent_id == account_id,
            models.CoaAccount.id != account_id,
        )
        .first()
        is not None
    )
    if has_children:
        raise HTTPException(
            status_code=409,
            detail="Account has child accounts and cannot be deleted",
        )

    db.delete(account)
    db.commit()


def seed_standard_coa(
    db: Session,
    tenant_id: int,
    user_id: int | None = None,
) -> list[dict]:
    """Seed a standard small-business COA for a new profile/tenant.

    Inserts all accounts from ``STANDARD_COA`` if no accounts exist yet for
    the given tenant.  Returns the created accounts as wire dicts.
    """
    _set_coa_tenant(db, tenant_id)

    existing = (
        db.query(models.CoaAccount)
        .filter(models.CoaAccount.tenant_id == tenant_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="COA already seeded for this tenant",
        )

    created = []
    for number, name, account_type, parent_number in STANDARD_COA:
        account = models.CoaAccount(
            tenant_id=tenant_id,
            number=number,
            name=name,
            type=account_type,
            parent_id=None,  # Root accounts for now; hierarchy can be set later
            is_active=True,
        )
        db.add(account)
        created.append(account)

    db.commit()
    for a in created:
        db.refresh(a)

    return [_coa_account_to_dict(a) for a in created]


def renumber_account(
    db: Session,
    account_id: int,
    tenant_id: int,
    new_number: int,
) -> dict:
    """Renumber an existing COA account.

    Validates the new number is within the account's type range and not
    already in use by another account in the same tenant.
    """
    _set_coa_tenant(db, tenant_id)
    account = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.id == account_id,
            models.CoaAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    range_min, range_max = NUMBERING_RANGES.get(account.type, (5000, 9999))
    if not (range_min <= new_number <= range_max):
        raise HTTPException(
            status_code=422,
            detail=f"Number {new_number} outside {account.type} range ({range_min}-{range_max})",
        )

    duplicate = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.tenant_id == tenant_id,
            models.CoaAccount.id != account_id,
            models.CoaAccount.number == new_number,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Account number already in use")

    account.number = new_number
    db.commit()
    db.refresh(account)
    return _coa_account_to_dict(account)


def reassign_parent(
    db: Session,
    account_id: int,
    tenant_id: int,
    new_parent_id: int | None,
) -> dict:
    """Reassign the parent of a COA account.

    Passing ``None`` or ``0`` clears the parent (makes it a root account).
    Validates that the new parent exists in the same tenant and is not the
    account itself (no cycles).
    """
    _set_coa_tenant(db, tenant_id)
    account = (
        db.query(models.CoaAccount)
        .filter(
            models.CoaAccount.id == account_id,
            models.CoaAccount.tenant_id == tenant_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if new_parent_id is None or new_parent_id == 0:
        account.parent_id = None
    else:
        if new_parent_id == account_id:
            raise HTTPException(status_code=400, detail="Account cannot be its own parent")
        parent = (
            db.query(models.CoaAccount)
            .filter(
                models.CoaAccount.id == new_parent_id,
                models.CoaAccount.tenant_id == tenant_id,
            )
            .first()
        )
        if parent is None:
            raise HTTPException(status_code=400, detail="Parent account not found")
        account.parent_id = new_parent_id

    db.commit()
    db.refresh(account)
    return _coa_account_to_dict(account)


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