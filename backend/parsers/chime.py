"""Chime checking and Credit Builder statement parser."""
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


def _looks_like_credit_builder(text: str) -> bool:
    return any(
        marker in text.lower()
        for marker in ["credit builder", "creditbuilder", "spotme"]
    )


def _extract_balances(text: str) -> Tuple[Optional[float], Optional[float]]:
    opening = None
    closing = None
    for m in re.finditer(r'(?:opening|starting)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        try:
            opening = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    for m in re.finditer(r'(?:closing|ending)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', text, re.IGNORECASE):
        try:
            closing = float(m.group(1).replace(',', ''))
        except ValueError:
            pass
    return opening, closing


def _find_section_lines(lines: List[str], header_texts: List[str]) -> Tuple[int, int]:
    """Find start/end indices of a section by header row."""
    start = -1
    end = len(lines)
    for i, line in enumerate(lines):
        if start == -1 and any(h.lower() in line.lower() for h in header_texts):
            start = i + 1
            continue
        if start != -1 and any(
            marker in line.lower()
            for marker in ["total", "summary", "ending balance", "beginning balance"]
        ):
            end = i
            break
    return start, end


def _parse_single_column(lines: List[str], year: int, is_credit_builder: bool) -> List[Dict[str, Any]]:
    transactions: List[Dict[str, Any]] = []
    seen: set = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Single-column Chime statements: MM/DD/YYYY Description Amount
        m = re.match(r'^(\d{1,2}/\d{1,2}/\d{4})\s+(.+?)\s+(-?[\$]?[0-9,]+\.\d{2})$', line)
        if not m:
            continue
        date = parse_date_us(m.group(1))
        if not date:
            continue
        desc = m.group(2).strip()
        amount_val = float(m.group(3).replace(',', '').replace('$', ''))
        desc_lower = desc.lower()

        if is_credit_builder:
            is_debit = not ("payment" in desc_lower or "deposit" in desc_lower or amount_val < 0)
        else:
            is_debit = not ("transfer from" in desc_lower or "direct deposit" in desc_lower or amount_val < 0)
        amount = normalize_signed_amount(abs(amount_val), is_debit)

        key = (date, desc, amount)
        if key in seen:
            continue
        seen.add(key)
        transactions.append(make_tx(date, desc, amount))

    return transactions


class ChimeParser:
    institution_name = "Chime"

    @classmethod
    def can_handle(cls, text: str) -> bool:
        tl = text.lower()
        return any(
            marker in tl
            for marker in ["chime", "chime checking", "spending account", "credit builder"]
        )

    @classmethod
    def parse(cls, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        lines = raw_text.splitlines()
        year = infer_year(raw_text)
        is_credit_builder = _looks_like_credit_builder(raw_text)

        start, end = _find_section_lines(
            lines,
            ["transactions", "transaction date", "spending", "purchases"],
        )
        if start == -1:
            start, end = 0, len(lines)

        transactions = _parse_single_column(lines[start:end], year, is_credit_builder)
        opening, closing = _extract_balances(raw_text)
        return build_parse_result(
            transactions,
            cls.institution_name,
            opening_balance=opening,
            closing_balance=closing,
            needs_review=len(transactions) == 0,
        )


def parse_chime_pdf(pdf_path: str, raw_text: str) -> Dict[str, Any]:
    return ChimeParser.parse(pdf_path, raw_text)
