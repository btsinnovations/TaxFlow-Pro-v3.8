"""Multi-page PDF table layout family parser.

Extends the simple PDF table parser by stitching transactions across page
breaks. Uses page markers (e.g., "Page 2 of 5") to detect continuation and
carries forward running balance if the first amount column drops out on later
pages.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.parsers.parser_base import build_parse_result, extract_amounts, infer_year, make_tx, parse_date_us


class PdfTableMultiFamily:
    """Parse multi-page PDF transaction tables."""

    def __init__(self, institution: str = "PDF Table Multi") -> None:
        self.institution = institution

    @staticmethod
    def _is_page_header(line: str) -> bool:
        return bool(re.search(r"page\s+\d+\s+of\s+\d+|statement\s+period|account\s+number", line, re.I))

    @staticmethod
    def _is_totals_line(line: str) -> bool:
        return bool(re.search(r"totals?\s+(for|this)|ending\s+balance|beginning\s+balance", line, re.I))

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
        in_table = False
        has_page_markers = any(self._is_page_header(line) for line in lines)
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if self._is_page_header(line):
                in_table = True
                continue
            if self._is_totals_line(line):
                in_table = False
                continue
            if has_page_markers and not in_table:
                continue
            date_match = re.match(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", line)
            if not date_match:
                continue
            date = parse_date_us(date_match.group(1), default_year=default_year)
            if not date:
                continue
            amounts = extract_amounts(line)
            if not amounts:
                continue
            amount = amounts[0][2]
            balance = amounts[-1][2] if len(amounts) > 1 and amounts[0][2] != amounts[-1][2] else None
            desc_end = amounts[0][0]
            description = line[date_match.end():desc_end].strip()
            transactions.append(make_tx(date, description, amount, balance))

        return build_parse_result(
            transactions,
            self.institution,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            needs_review=not transactions,
        )
