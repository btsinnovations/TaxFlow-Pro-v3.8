"""Simple single-page PDF table layout family parser.

Uses regex-based line parsing on extracted text. Optimized for regional banks
and credit unions whose statements fit a single-page transaction table.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.parsers.parser_base import build_parse_result, extract_amounts, infer_year, make_tx, parse_date_us


class PdfTableSimpleFamily:
    """Parse simple single-page PDF transaction tables."""

    def __init__(self, institution: str = "PDF Table Simple") -> None:
        self.institution = institution

    def parse(
        self,
        content: bytes,
        filename: Optional[str] = None,
        opening_balance: Optional[float] = None,
        closing_balance: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        text = content.decode("utf-8", errors="replace")
        default_year = infer_year(text)
        transactions: List[Dict[str, Any]] = []
        lines = text.splitlines()
        # Skip header until we find a date line
        in_table = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            date_match = re.match(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", line)
            if date_match:
                in_table = True
            if not in_table:
                continue
            date = parse_date_us(date_match.group(1), default_year=default_year) if date_match else None
            if not date:
                continue
            amounts = extract_amounts(line)
            if not amounts:
                continue
            # Use the left-most amount as transaction amount; right-most as running balance.
            amount = amounts[0][2]
            balance = amounts[-1][2] if len(amounts) > 1 and amounts[0][2] != amounts[-1][2] else None
            # Description is everything between date and the first amount
            desc_start = date_match.end()
            desc_end = amounts[0][0]
            description = line[desc_start:desc_end].strip()
            transactions.append(make_tx(date, description, amount, balance))

        return build_parse_result(
            transactions,
            self.institution,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            needs_review=not transactions,
        )
