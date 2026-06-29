import re
from typing import Tuple, Set
from .models import Transaction
from .config import TAX_RULES

def normalize_tokens(text: str) -> Set[str]:
    """Strip punctuation, lowercase, split into tokens."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return set(cleaned.split())

def match_keyword(keyword: str, text: str) -> bool:
    """Precision‑first token subset matching."""
    kw_tokens = normalize_tokens(keyword)
    text_tokens = normalize_tokens(text)
    return kw_tokens.issubset(text_tokens)

def classify_transaction(txn: Transaction) -> Tuple[str, str, bool]:
    if txn.is_tombstone:
        return "tombstone", "", False

    # Build search text: description + category if meaningful
    text = txn.description.lower()
    if txn.category and txn.category.lower() not in ["uncategorized", "misc", ""]:
        text += f" {txn.category.lower()}"

    # Phase 1: high precision token subset
    for kw, cat, line, ded in TAX_RULES:
        if match_keyword(kw, text):
            return cat, line, ded

    # Phase 2: guarded substring fallback
    for kw, cat, line, ded in TAX_RULES:
        kw_low = kw.lower()
        if len(kw_low) >= 5 and kw_low in text:
            return cat, line, ded
        elif kw_low in text and kw_low in normalize_tokens(text):
            return cat, line, ded

    return "uncategorized", "", False

def apply_tax(graph):
    for txn in graph.all():
        cat, line, ded = classify_transaction(txn)
        txn.tax_category = cat
        txn.tax_line = line
        txn.tax_deductible = ded