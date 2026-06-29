"""Shared base helpers for backend/parsers institution-specific modules."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


def parse_date_us(date_str: str, default_year: Optional[int] = None) -> Optional[str]:
    """Convert MM/DD/YYYY, MM/DD/YY, MM/DD, or YYYY-MM-DD to ISO date string."""
    date_str = date_str.strip()
    # Handle MM/DD without year by appending default year
    if re.match(r"^\d{1,2}/\d{1,2}$", date_str) and default_year:
        date_str = f"{date_str}/{default_year}"
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, fmt)
            if fmt == "%m/%d/%y" and default_year:
                dt = dt.replace(year=default_year % 100 + (default_year // 100) * 100)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_amounts(line: str) -> List[Tuple[int, int, float]]:
    """Return all dollar amounts in a line as (start, end, value)."""
    out: List[Tuple[int, int, float]] = []
    for m in re.finditer(r'[\$\-]?([0-9,]+\.\d{2})', line):
        try:
            val = float(m.group(1).replace(',', ''))
        except ValueError:
            continue
        out.append((m.start(), m.end(), val))
    return out


def infer_year(text: str, default: int = 2025) -> int:
    """Find a likely statement year in the first few lines of text."""
    m = re.search(r'\b(20\d{2})\b', text[:500])
    if m:
        return int(m.group(1))
    return default


def normalize_signed_amount(raw: float, is_debit: bool = False) -> float:
    """Return negative for debits/charges, positive for credits/payments."""
    if is_debit:
        return -abs(raw)
    return abs(raw)


DEBIT_KEYWORDS: set[str] = {
    "withdrawal", "withdraw", "atm", "debit", "purchase", "fee", "charge",
    "bill", "payment to", "transfer to", "grocery", "supermarket",
    "annual fee", "late fee", "interest charge",
}
CREDIT_KEYWORDS: set[str] = {
    "deposit", "direct deposit", "paycheck", "credit", "refund",
    "return", "dividend", "interest", "reward", "cashback", "transfer in",
    "wire in", "ach in", "contribution", "payment received", "dividend received",
    "interest earned", "interest paid", "sale of",
}


def infer_transaction_sign(description: str, default_positive: bool = True) -> int:
    """Return +1 for credit/deposit and -1 for debit/withdrawal based on description."""
    lowered = description.lower()
    if any(kw in lowered for kw in DEBIT_KEYWORDS):
        return -1
    if any(kw in lowered for kw in CREDIT_KEYWORDS):
        return 1
    return 1 if default_positive else -1


def make_tx(date: str, desc: str, amount: float, balance: Optional[float] = None, force_sign: Optional[int] = None) -> Dict[str, Any]:
    """Build a GenericPDFParser-compatible transaction dict."""
    sign = force_sign if force_sign in (1, -1) else infer_transaction_sign(desc)
    signed = abs(amount) * sign
    return {
        "date": date,
        "description": desc.strip(),
        "amount": float(signed),
        "type": "debit" if signed < 0 else "credit",
        "balance": float(balance) if balance is not None else None,
        "tax_flag": None,
    }


def build_parse_result(
    transactions: List[Dict[str, Any]],
    institution: str,
    opening_balance: Optional[float] = None,
    closing_balance: Optional[float] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    needs_review: bool = False,
) -> Dict[str, Any]:
    """Return a result dict matching GenericPDFParser.parse() shape."""
    tx_sum = sum(t.get("amount") or 0.0 for t in transactions)
    variance = None
    if opening_balance is not None and closing_balance is not None:
        variance = round(closing_balance - opening_balance - tx_sum, 2)
    return {
        "template": institution,
        "account_info": {
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "template_name": institution,
            "institution": institution,
        },
        "transactions": transactions,
        "reconciliation": {
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "transaction_sum": round(tx_sum, 2),
            "variance": variance,
            "balanced": variance == 0.0 if variance is not None else None,
        },
        "meta": {
            "total_pages": 1,
            "total_raw_transactions": len(transactions),
            "duplicates_removed": 0,
            "period_start": period_start,
            "period_end": period_end,
            "parser": "institution_specific",
        },
        "needs_review": needs_review,
    }
