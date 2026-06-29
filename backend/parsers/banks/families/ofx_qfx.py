"""OFX/QFX layout family parser.

Wraps OFX parsing for Quicken/QuickBooks export formats produced by most major
and many regional banks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.parsers.parser_base import build_parse_result, normalize_signed_amount, parse_date_us


class OfxQfxFamily:
    """Parse OFX/QFX statement files."""

    def __init__(self, institution: str = "OFX/QFX") -> None:
        self.institution = institution

    def _parse_ofx_date(self, raw: str) -> Optional[str]:
        # OFX dates look like 20250115 or 20250115120000[0:GMT]
        if not raw or len(raw) < 8:
            return None
        try:
            year = int(raw[:4])
            month = int(raw[4:6])
            day = int(raw[6:8])
            from datetime import date
            return date(year, month, day).isoformat()
        except (ValueError, TypeError):
            return None

    def _strip_xml(self, content: bytes) -> str:
        # OFX files are SGML/XML hybrids. Strip the HTTP/OFX header and use simple tag extraction.
        text = content.decode("utf-8", errors="replace")
        if "OFXHEADER:" in text:
            # Split after the blank line that terminates the OFX header
            parts = text.split("\n\n", 1)
            if len(parts) > 1:
                text = parts[1]
        return text

    def _extract_transactions(self, text: str) -> List[Dict[str, Any]]:
        transactions: List[Dict[str, Any]] = []
        # Split on transaction open tags and extract fields
        import re

        # Find each <STMTTRN> ... </STMTTRN> block
        for block in re.split(r"<STMTTRN[>\s]", text)[1:]:
            block = block.split("</STMTTRN>", 1)[0]
            fields: Dict[str, str] = {}
            for tag in ("TRNTYPE", "DTPOSTED", "DTUSER", "TRNAMT", "FITID", "NAME", "MEMO"):
                m = re.search(rf"<{tag}>([^<]+)", block)
                if m:
                    fields[tag] = m.group(1).strip()
            if not fields.get("DTPOSTED") or not fields.get("TRNAMT"):
                continue
            date = self._parse_ofx_date(fields["DTPOSTED"])
            if not date:
                continue
            try:
                amount = float(fields["TRNAMT"].replace(",", ""))
            except ValueError:
                continue
            trn_type = fields.get("TRNTYPE", "").upper()
            is_debit = trn_type in {"DEBIT", "CHECK", "ATM", "PAYMENT", "FEE"} or amount < 0
            amount = normalize_signed_amount(amount, is_debit=is_debit)
            desc = fields.get("NAME") or fields.get("MEMO") or ""
            transactions.append(
                {
                    "date": date,
                    "description": desc.strip(),
                    "amount": amount,
                    "type": "debit" if amount < 0 else "credit",
                    "balance": None,
                    "tax_flag": None,
                }
            )
        return transactions

    def parse(
        self,
        content: bytes,
        filename: Optional[str] = None,
        opening_balance: Optional[float] = None,
        closing_balance: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        text = self._strip_xml(content)
        transactions = self._extract_transactions(text)
        return build_parse_result(
            transactions,
            self.institution,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            needs_review=not transactions,
        )
