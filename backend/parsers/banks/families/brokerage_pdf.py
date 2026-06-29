"""Brokerage statement PDF layout family parser.

Focuses on cash/money-market transactions (deposits, withdrawals, trades, dividends,
interest). Holdings tables and positions are intentionally out of scope for v3.11.6.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.parsers.parser_base import build_parse_result, extract_amounts, infer_year, normalize_signed_amount, parse_date_us


class BrokeragePdfFamily:
    """Parse brokerage cash-transaction sections."""

    INCOME_KEYWORDS = {"dividend", "interest", "capital gain", "short-term gain", "long-term gain"}
    WITHDRAWAL_KEYWORDS = {"withdrawal", "wire out", "ach out", "transfer out"}
    DEPOSIT_KEYWORDS = {"deposit", "wire in", "ach in", "transfer in", "contribution"}
    TRADE_KEYWORDS = {"buy", "sell", "purchase", "sale of"}

    def __init__(self, institution: str = "Brokerage PDF") -> None:
        self.institution = institution

    @staticmethod
    def _classify(description: str) -> str:
        lowered = description.lower()
        if any(kw in lowered for kw in BrokeragePdfFamily.INCOME_KEYWORDS):
            return "income"
        if any(kw in lowered for kw in BrokeragePdfFamily.WITHDRAWAL_KEYWORDS):
            return "withdrawal"
        if any(kw in lowered for kw in BrokeragePdfFamily.DEPOSIT_KEYWORDS):
            return "deposit"
        if any(kw in lowered for kw in BrokeragePdfFamily.TRADE_KEYWORDS):
            return "trade"
        return "other"

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
        in_cash_section = False
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if re.search(r"cash\s+transactions|money\s+market\s+transactions|account\s+activity", line, re.I):
                in_cash_section = True
                continue
            if re.search(r"holdings|positions|open\s+orders", line, re.I):
                in_cash_section = False
                continue

            # If we're inside the cash section, parse date lines.
            # Otherwise only parse lines that clearly start with a date and have a dollar amount.
            date_match = re.match(r"^(\d{1,2}/\d{1,2}/\d{2,4})", line)
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

            category = self._classify(description)
            is_debit = category in {"withdrawal", "trade"} and "buy" in description.lower()
            if category == "income":
                amount = abs(amount)
            elif category == "withdrawal":
                amount = -abs(amount)
            elif category == "deposit":
                amount = abs(amount)
            elif category == "trade":
                amount = normalize_signed_amount(amount, is_debit=is_debit)
            else:
                amount = normalize_signed_amount(amount, is_debit=amount < 0)

            tx_type = "debit" if amount < 0 else "credit"
            transactions.append(
                {
                    "date": date,
                    "description": description,
                    "amount": amount,
                    "type": tx_type,
                    "balance": balance,
                    "tax_flag": None,
                }
            )

        return build_parse_result(
            transactions,
            self.institution,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            needs_review=not transactions,
        )
