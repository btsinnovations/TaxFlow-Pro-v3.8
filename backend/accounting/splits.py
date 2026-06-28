"""Transaction splits validation and helpers for TaxFlow Pro v3.11.6 B2.

A transaction split divides a single transaction into multiple line items,
each with its own COA account and amount. Splits are stored as JSON in
``transactions.splits``.

Validation rules:
- Sum of split amounts must equal transaction total (within rounding tolerance).
- No empty account IDs.
- No zero amounts.
- No duplicate splits (same account + amount combination).
"""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


# Rounding tolerance: 2 decimal places for monetary amounts.
TOLERANCE = Decimal("0.01")


class SplitsError(Exception):
    """Domain-level split validation error."""


def _to_decimal(value: Any) -> Decimal:
    """Convert a value to Decimal."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return Decimal(str(value))


def validate_splits(
    splits: list[dict],
    transaction_total: Decimal | float | str,
    *,
    tolerance: Optional[Decimal] = None,
) -> list[dict]:
    """Validate split line items against a transaction total.

    Args:
        splits: List of split dicts, each with at least:
            - account_id (int): COA account ID.
            - amount (float/str/Decimal): Split amount.
            - memo (str, optional): Split memo.
            - category (str, optional): Split category.
        transaction_total: The total amount of the parent transaction.
        tolerance: Rounding tolerance (default: 0.01).

    Returns:
        The validated and normalized splits list.

    Raises:
        SplitsError: If any validation rule is violated.
    """
    if not splits:
        return []

    if tolerance is None:
        tolerance = TOLERANCE

    total = _to_decimal(transaction_total)
    split_sum = Decimal("0")
    seen = set()

    for i, split in enumerate(splits):
        account_id = split.get("account_id")
        amount = split.get("amount")

        if account_id is None or account_id == "":
            raise SplitsError(f"Split {i}: account_id is required")

        if amount is None or _to_decimal(amount) == Decimal("0"):
            raise SplitsError(f"Split {i}: amount must be non-zero")

        amount_dec = _to_decimal(amount)
        split_sum += amount_dec

        # Check for duplicates: same account_id + amount combination.
        key = (account_id, str(amount_dec))
        if key in seen:
            raise SplitsError(f"Split {i}: duplicate split (account_id={account_id}, amount={amount})")
        seen.add(key)

    # Check sum matches total within tolerance.
    diff = abs(split_sum - total)
    if diff > tolerance:
        raise SplitsError(
            f"Split sum ({split_sum}) does not match transaction total ({total}) "
            f"within tolerance ({tolerance}); difference: {diff}"
        )

    return splits


def set_splits(
    db: Session,
    transaction_id: int,
    tenant_id: int,
    user_id: int,
    splits: list[dict],
) -> models.Transaction:
    """Set the splits JSON on a transaction after validation."""
    tx = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.user_id == user_id,
        )
        .first()
    )
    if tx is None:
        raise SplitsError("Transaction not found")

    validated = validate_splits(splits, tx.amount or Decimal("0"))
    tx.splits = json.dumps(validated)
    db.commit()
    db.refresh(tx)
    return tx


def get_splits(tx: models.Transaction) -> list[dict]:
    """Parse the splits JSON from a transaction."""
    if not tx.splits:
        return []
    try:
        data = json.loads(tx.splits)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def migrate_single_line_to_splits(tx: models.Transaction) -> models.Transaction:
    """Migrate a pre-existing single-line transaction to have a one-entry split.

    If the transaction has no splits, create a single split entry that
    matches the transaction's amount and COA account (if any).
    """
    existing = get_splits(tx)
    if existing:
        return tx  # Already has splits

    split_entry = {
        "account_id": tx.coa_account_id or tx.gl_account_id,
        "amount": float(tx.amount) if tx.amount is not None else 0.0,
        "memo": tx.description,
        "category": tx.category,
    }
    if split_entry["account_id"] is None:
        # Can't create a split without an account; leave as-is.
        return tx

    tx.splits = json.dumps([split_entry])
    return tx


def apply_pre_post_allocation(
    splits: list[dict],
    pre_allocation: Optional[dict] = None,
    post_allocation: Optional[dict] = None,
) -> list[dict]:
    """Apply pre/post allocations to splits.

    Pre-allocations (e.g., ATM cash back) are inserted before the main splits.
    Post-allocations are appended after.

    Each allocation is a dict with account_id, amount, and optional memo.
    """
    result = []

    if pre_allocation:
        result.append(pre_allocation)

    result.extend(splits)

    if post_allocation:
        result.append(post_allocation)

    return result