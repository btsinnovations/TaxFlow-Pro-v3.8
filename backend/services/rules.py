"""Categorization rule engine for TaxFlow Pro v3.9.

Rules match transaction descriptions/vendors against a case-insensitive
substring or simple wildcard pattern. The highest-priority enabled rule wins.
"""
from __future__ import annotations

import fnmatch
from typing import Iterable, List, Optional

from .. import models


def _matches(description: Optional[str], pattern: str) -> bool:
    if not description:
        return False
    text = description.lower()
    pat = pattern.lower()
    if "*" in pat or "?" in pat:
        return fnmatch.fnmatch(text, pat)
    return pat in text


def apply_rules(
    transactions: Iterable[models.Transaction],
    rules: Iterable[models.CategorizationRule],
) -> List[models.Transaction]:
    """Apply enabled rules to transactions, mutating the highest-priority match.

    Returns the same transaction objects with `category` and `gl_account_id`
    updated when a rule matches. Rules are evaluated by priority descending,
    then by id ascending for deterministic tie-breaking.
    """
    active_rules = sorted(
        [r for r in rules if r.enabled],
        key=lambda r: (-r.priority, r.id),
    )
    for tx in transactions:
        for rule in active_rules:
            if _matches(tx.description, rule.pattern):
                tx.category = rule.name
                tx.gl_account_id = rule.gl_account_id
                break
    return list(transactions)
