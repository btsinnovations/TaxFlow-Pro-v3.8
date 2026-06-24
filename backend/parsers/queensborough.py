"""Queensborough National Bank & Trust (QNB) statement parser."""
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


class QueensboroughParser:
    institution_name = "Queensborough National Bank"

    @classmethod
    def can_handle(cls, text: str) -> bool:
        tl = text.lower()
        return any(
            marker in tl
            for marker in [
                "queensborough national bank",
                "queensborough bank & trust",
                "queensborough bank and trust",
                "qnb",
            ]
        )

    @classmethod
    def parse(cls, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        transactions: List[Dict[str, Any]] = []
        seen: set = set()
        opening = None
        closing = None

        for m in re.finditer(r'(?:beginning|previous|opening)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', raw_text, re.IGNORECASE):
            try:
                opening = float(m.group(1).replace(',', ''))
            except ValueError:
                pass
        for m in re.finditer(r'(?:ending|closing|current)\s+balance[^0-9]*\$?\s*([0-9,]+\.\d{2})', raw_text, re.IGNORECASE):
            try:
                closing = float(m.group(1).replace(',', ''))
            except ValueError:
                pass

        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\$]?[0-9,]+\.\d{2})(?:\s+[\$]?[0-9,]+\.\d{2})?$', line)
            if not m:
                continue
            date = parse_date_us(m.group(1))
            if not date:
                continue
            desc = m.group(2).strip()
            amount_val = float(m.group(3).replace(',', '').replace('$', ''))

            is_debit = not ("deposit" in desc.lower() or "credit" in desc.lower() or amount_val < 0)
            amount = normalize_signed_amount(abs(amount_val), is_debit)

            key = (date, desc, amount)
            if key in seen:
                continue
            seen.add(key)
            transactions.append(make_tx(date, desc, amount))

        return build_parse_result(
            transactions,
            cls.institution_name,
            opening_balance=opening,
            closing_balance=closing,
            needs_review=len(transactions) == 0,
        )


def parse_queensborough_pdf(pdf_path: str, raw_text: str) -> Dict[str, Any]:
    return QueensboroughParser.parse(pdf_path, raw_text)
