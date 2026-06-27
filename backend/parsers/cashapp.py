"""Cash App statement parser (ported from phase3_pipeline).

Cash App uses a peer-to-peer format with To/From semantics and
single-column amounts with +/- sign indicators.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .parser_base import (
    build_parse_result, infer_year, make_tx, normalize_signed_amount,
)


def _extract_balances(text: str) -> Tuple[Optional[float], Optional[float]]:
    opening, closing = None, None
    for m in re.finditer(r'(?:previous|opening|beginning)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        opening = float(m.group(1).replace(',', ''))
    for m in re.finditer(r'(?:new|closing|ending|current)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        closing = float(m.group(1).replace(',', ''))
    return opening, closing


def _parse_lines(text: str) -> List[Dict[str, Any]]:
    """Cash App layout: Mon DD Description $Amount [To/From semantics].

    Lines start with a 3-letter month abbreviation and day number.
    Amounts may have + prefix for credits, no prefix (or -) for debits.
    """
    transactions: List[Dict[str, Any]] = []
    year = infer_year(text)
    seen: set = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or any(s in line.lower() for s in ["subtotal", "total", "page", "statement period"]):
            continue

        # Match: Mon DD Description ... $Amount or +$Amount
        m = re.match(r'^([A-Za-z]{3})\s+(\d{1,2})\s+(.+?)\s+([+\-]?\$?\d+(?:\.\d{2})?)$', line)
        if not m:
            continue

        month_str = m.group(1)
        day_str = m.group(2)
        desc = m.group(3).strip()
        amount_str = m.group(4).replace('$', '').replace(',', '')

        # Parse date
        try:
            date_obj = datetime.strptime(f"{month_str} {day_str} {year}", "%b %d %Y")
            date_str = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue

        # Parse amount with sign
        is_credit = amount_str.startswith('+')
        amount_str = amount_str.lstrip('+-')
        try:
            raw_amount = float(amount_str)
        except ValueError:
            continue

        amount = abs(raw_amount) if is_credit else -abs(raw_amount)

        key = (date_str, desc, amount)
        if key in seen:
            continue
        seen.add(key)
        transactions.append(make_tx(date_str, desc, amount))

    return transactions


class CashAppParser:
    institution_name = "Cash App"

    @classmethod
    def can_handle(cls, text: str) -> bool:
        tl = text.lower()
        return "cash app" in tl or "cashapp" in tl

    @classmethod
    def parse(cls, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        opening, closing = _extract_balances(raw_text)
        transactions = _parse_lines(raw_text)
        return build_parse_result(
            transactions, cls.institution_name,
            opening_balance=opening, closing_balance=closing,
            needs_review=len(transactions) == 0,
        )


def parse_cashapp_pdf(pdf_path: str, raw_text: str) -> Dict[str, Any]:
    return CashAppParser.parse(pdf_path, raw_text)