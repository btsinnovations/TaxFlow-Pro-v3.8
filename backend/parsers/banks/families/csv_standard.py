"""CSV-standard layout family parser.

Handles bank statement CSV exports with a single header row and columns such as
Date, Description, Amount, Balance. Institution-specific column names are mapped
via a normalization table.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from backend.parsers.parser_base import parse_date_us, normalize_signed_amount, build_parse_result


class CsvStandardFamily:
    """Parse generic bank CSV exports."""

    DATE_ALIASES = {"date", "posted date", "transaction date", "trans date"}
    DESC_ALIASES = {"description", "memo", "payee", "transaction", "name", "details"}
    AMOUNT_ALIASES = {"amount", "transaction amount"}
    DEBIT_ALIASES = {"debit", "debit amount", "money out"}
    CREDIT_ALIASES = {"credit", "credit amount", "money in"}
    BALANCE_ALIASES = {"balance", "running balance"}
    TYPE_ALIASES = {"type", "transaction type"}

    def __init__(self, institution: str = "CSV Standard") -> None:
        self.institution = institution

    @staticmethod
    def _normalize_header(header: str) -> str:
        return header.strip().lower().replace("_", " ")

    def _map_columns(self, headers: List[str]) -> Dict[str, Optional[int]]:
        """Map raw CSV headers to canonical field names."""
        mapped: Dict[str, Optional[int]] = {
            "date": None,
            "description": None,
            "amount": None,
            "debit": None,
            "credit": None,
            "balance": None,
            "type": None,
        }
        for idx, raw in enumerate(headers):
            norm = self._normalize_header(raw)
            if mapped["date"] is None and norm in self.DATE_ALIASES:
                mapped["date"] = idx
            elif mapped["description"] is None and norm in self.DESC_ALIASES:
                mapped["description"] = idx
            elif mapped["amount"] is None and norm in self.AMOUNT_ALIASES:
                mapped["amount"] = idx
            elif mapped["debit"] is None and norm in self.DEBIT_ALIASES:
                mapped["debit"] = idx
            elif mapped["credit"] is None and norm in self.CREDIT_ALIASES:
                mapped["credit"] = idx
            elif mapped["balance"] is None and norm in self.BALANCE_ALIASES:
                mapped["balance"] = idx
            elif mapped["type"] is None and norm in self.TYPE_ALIASES:
                mapped["type"] = idx
        return mapped

    def _extract_amount(self, row: List[str], mapping: Dict[str, Optional[int]]) -> Optional[float]:
        if mapping["amount"] is not None:
            raw = row[mapping["amount"]].strip().replace(",", "")
            if raw:
                return float(raw)
        debit = credit = None
        if mapping["debit"] is not None:
            raw = row[mapping["debit"]].strip().replace(",", "")
            if raw:
                debit = float(raw)
        if mapping["credit"] is not None:
            raw = row[mapping["credit"]].strip().replace(",", "")
            if raw:
                credit = float(raw)
        if debit and credit:
            return normalize_signed_amount(debit or credit, is_debit=bool(debit))
        if debit:
            return -abs(debit)
        if credit:
            return abs(credit)
        return None

    def parse(
        self,
        content: bytes,
        filename: Optional[str] = None,
        opening_balance: Optional[float] = None,
        closing_balance: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        text = content.decode("utf-8", errors="replace")
        dialect = csv.Sniffer().sniff(text[:2048]) if text[:2048] else None
        reader = csv.reader(io.StringIO(text), dialect=dialect)
        rows = list(reader)
        if not rows:
            return build_parse_result([], self.institution, needs_review=True)

        headers = rows[0]
        mapping = self._map_columns(headers)
        if mapping["date"] is None or mapping["description"] is None:
            return build_parse_result([], self.institution, needs_review=True)

        transactions: List[Dict[str, Any]] = []
        default_year = kwargs.get("statement_year") or 2025
        for row in rows[1:]:
            if not row or not any(cell.strip() for cell in row):
                continue
            if mapping["date"] >= len(row) or mapping["description"] >= len(row):
                continue
            date_raw = row[mapping["date"]].strip()
            date = parse_date_us(date_raw, default_year=default_year)
            if not date:
                continue
            desc = row[mapping["description"]].strip()
            amount = self._extract_amount(row, mapping)
            balance = None
            if mapping["balance"] is not None and mapping["balance"] < len(row):
                bal_raw = row[mapping["balance"]].strip().replace(",", "")
                if bal_raw:
                    try:
                        balance = float(bal_raw)
                    except ValueError:
                        pass
            if amount is None:
                continue
            tx_type = "debit" if amount < 0 else "credit"
            transactions.append(
                {
                    "date": date,
                    "description": desc,
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
