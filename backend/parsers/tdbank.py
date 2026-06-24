"""TD Bank checking and credit-card statement parser."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .parser_base import (
    build_parse_result,
    extract_amounts,
    infer_year,
    make_tx,
    normalize_signed_amount,
    parse_date_us,
)


def _looks_like_credit(text: str) -> bool:
    tl = text.lower()
    return any(
        marker in tl
        for marker in [
            "td bank credit",
            "td cash",
            "td first class",
            "td business credit",
            "credit card",
        ]
    )


def _extract_balances(text: str) -> Tuple[Optional[float], Optional[float]]:
    opening = None
    closing = None
    for m in re.finditer(r'(?:previous|opening|beginning)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        try:
            opening = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    for m in re.finditer(r'(?:new|closing|ending|current)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        try:
            closing = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    return opening, closing


def _parse_checking_lines(text: str) -> List[Dict[str, Any]]:
    """TD checking layout: MM/DD Description Amount [Balance]."""
    transactions: List[Dict[str, Any]] = []
    year = infer_year(text)
    seen: set = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or "Subtotal" in line or "Total" in line.lower():
            continue
        m = re.match(r'^(\d{2}/\d{2})\s+(.+?)\s+(-?[\$]?[0-9,]+\.\d{2})\s*(?:[\$]?[0-9,]+\.\d{2})?$', line)
        if not m:
            continue
        date_str = f"{year}-{m.group(1).replace('/', '-')}"
        desc = m.group(2).strip()
        amount_val = float(m.group(3).replace(',', '').replace('$', ''))

        desc_upper = desc.upper()
        is_debit = any(
            k in desc_upper
            for k in ["DEBIT", "WITHDRAWAL", "PAYMENT", "FEE", "CHARGE", "CHECK"]
        )
        amount = normalize_signed_amount(amount_val, is_debit)

        key = (date_str, desc, amount)
        if key in seen:
            continue
        seen.add(key)
        transactions.append(make_tx(date_str, desc, amount))

    return transactions


def _parse_credit_lines(text: str) -> List[Dict[str, Any]]:
    """TD credit layout: MM/DD/YYYY Description Amount [Balance]."""
    transactions: List[Dict[str, Any]] = []
    seen: set = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or any(skip in line.lower() for skip in ["transactions", "totals", "payments", "credits", "page"]):
            continue
        m = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\$]?[0-9,]+\.\d{2})(?:\s+[\$]?[0-9,]+\.\d{2})?$', line)
        if not m:
            continue
        date = parse_date_us(m.group(1))
        if not date:
            continue
        desc = m.group(2).strip()
        amount_val = float(m.group(3).replace(',', '').replace('$', ''))
        # Charges are positive in statement; treat as debits. Payments/credits are negative or labeled.
        is_debit = not ("payment" in desc.lower() or "credit" in desc.lower() or amount_val < 0)
        amount = normalize_signed_amount(abs(amount_val), is_debit)

        key = (date, desc, amount)
        if key in seen:
            continue
        seen.add(key)
        transactions.append(make_tx(date, desc, amount))

    return transactions


class TDBankParser:
    institution_name = "TD Bank"

    @classmethod
    def can_handle(cls, text: str) -> bool:
        tl = text.lower()
        return "td bank" in tl or "tdbusiness" in tl or _looks_like_credit(text)

    @classmethod
    def parse(cls, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        opening, closing = _extract_balances(raw_text)
        if _looks_like_credit(raw_text):
            transactions = _parse_credit_lines(raw_text)
        else:
            transactions = _parse_checking_lines(raw_text)
        return build_parse_result(
            transactions,
            cls.institution_name,
            opening_balance=opening,
            closing_balance=closing,
            needs_review=len(transactions) == 0,
        )


def parse_td_bank_pdf(pdf_path: str, raw_text: str) -> Dict[str, Any]:
    return TDBankParser.parse(pdf_path, raw_text)
