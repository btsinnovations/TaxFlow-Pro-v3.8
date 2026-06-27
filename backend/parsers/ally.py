"""Ally Bank statement parser."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .parser_base import (
    build_parse_result, infer_year, make_tx, normalize_signed_amount, parse_date_us,
)


def _extract_balances(text: str) -> Tuple[Optional[float], Optional[float]]:
    opening, closing = None, None
    for m in re.finditer(r'(?:previous|opening|beginning)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        opening = float(m.group(1).replace(',', ''))
    for m in re.finditer(r'(?:new|closing|ending|current)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        closing = float(m.group(1).replace(',', ''))
    return opening, closing


def _parse_lines(text: str) -> List[Dict[str, Any]]:
    """Ally Bank layout: MM/DD Description Debit Credit [Balance]."""
    transactions: List[Dict[str, Any]] = []
    year = infer_year(text)
    seen: set = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or any(s in line.lower() for s in ["subtotal", "total", "page", "statement period"]):
            continue
        m = re.match(
            r'^(\d{2}/\d{2})\s+(.+?)\s+(-?\$?[0-9,]+\.\d{2})?\s*(-?\$?[0-9,]+\.\d{2})?\s*(-?\$?[0-9,]+\.\d{2})?$',
            line,
        )
        if not m:
            continue
        date_str = f"{year}-{m.group(1).replace('/', '-')}"
        desc = m.group(2).strip()
        amounts = []
        for g in [m.group(3), m.group(4), m.group(5)]:
            if g:
                amounts.append(float(g.replace(',', '').replace('$', '')))
        if not amounts:
            continue

        desc_upper = desc.upper()
        is_debit = any(k in desc_upper for k in ["WITHDRAWAL", "DEBIT", "PAYMENT", "FEE", "CHARGE", "PURCHASE", "CHECK"])
        is_credit = any(k in desc_upper for k in ["DEPOSIT", "CREDIT", "REFUND", "REVERSAL", "SALARY", "INTEREST"])

        if is_credit and len(amounts) >= 2:
            amount = abs(amounts[1]) if amounts[1] else abs(amounts[0])
        elif is_debit or len(amounts) >= 1:
            amount = -abs(amounts[0])
        else:
            amount = amounts[0]

        key = (date_str, desc, amount)
        if key in seen:
            continue
        seen.add(key)
        transactions.append(make_tx(date_str, desc, amount))
    return transactions


class AllyBankParser:
    institution_name = "Ally Bank"

    @classmethod
    def can_handle(cls, text: str) -> bool:
        tl = text.lower()
        return "ally bank" in tl or "ally" in tl

    @classmethod
    def parse(cls, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        opening, closing = _extract_balances(raw_text)
        transactions = _parse_lines(raw_text)
        return build_parse_result(
            transactions, cls.institution_name,
            opening_balance=opening, closing_balance=closing,
            needs_review=len(transactions) == 0,
        )


def parse_ally_pdf(pdf_path: str, raw_text: str) -> Dict[str, Any]:
    return AllyBankParser.parse(pdf_path, raw_text)
