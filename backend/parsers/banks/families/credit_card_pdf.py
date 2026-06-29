"""Credit-card statement PDF layout family parser.

Handles credit-card-specific quirks: posting date vs transaction date,
payments/credits as positive, purchases/fees as negative, and reward
redemptions.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.parsers.parser_base import build_parse_result, extract_amounts, infer_year, normalize_signed_amount, parse_date_us


class CreditCardPdfFamily:
    """Parse credit-card statement PDFs."""

    PAYMENT_KEYWORDS = {"payment", "payment - thank you", "credit", "reward", "cashback", "return", "refund"}
    FEE_KEYWORDS = {"fee", "interest charge", "finance charge", "annual fee", "late fee"}

    def __init__(self, institution: str = "Credit Card PDF") -> None:
        self.institution = institution

    @staticmethod
    def _is_payment_line(line: str) -> bool:
        lowered = line.lower()
        return any(kw in lowered for kw in CreditCardPdfFamily.PAYMENT_KEYWORDS)

    @staticmethod
    def _is_fee_line(line: str) -> bool:
        lowered = line.lower()
        return any(kw in lowered for kw in CreditCardPdfFamily.FEE_KEYWORDS)

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
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            # Credit-card statements often have two dates: transaction and posting.
            # Accept formats like "01/02/2026 01/03/2026" or "01/02 01/03".
            date_match = re.match(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)(?:\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?)?", line)
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
            # Description is everything between the date(s) and the first amount.
            desc_end = amounts[0][0]
            description = line[date_match.end():desc_end].strip()

            is_payment = self._is_payment_line(description)
            is_fee = self._is_fee_line(description)
            if is_payment:
                amount = abs(amount)
            elif is_fee:
                amount = -abs(amount)
            else:
                # Default: purchases negative, refunds positive
                amount = normalize_signed_amount(amount, is_debit=not is_payment)

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
