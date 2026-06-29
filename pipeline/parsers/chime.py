"""Chime Credit Builder parser."""
import re
from typing import List, Dict

from ..models import Transaction
from .base import (
    BaseParser, normalize_date, normalize_signed_amount,
    extract_amount_from_line, generate_stable_uid, collision_key
)
from . import register_parser

@register_parser
class ChimeParser(BaseParser):
    institution_name = "Chime"
    priority = 80

    def can_handle(self, text: str) -> bool:
        return "chime" in text.lower()

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        lines = text.splitlines()
        collision_map: Dict[tuple, int] = {}

        # Locate sections
        trans_header = -1
        payments_header = -1
        for i, line in enumerate(lines):
            if "TRANSACTION DATE" in line and "AMOUNT" in line:
                trans_header = i
            if line.strip() == "Payments" and i > trans_header:
                payments_header = i
                break

        # Process Transactions section (purchases, transfers)
        if trans_header != -1:
            end_idx = payments_header if payments_header != -1 else len(lines)
            for line in lines[trans_header+1:end_idx]:
                line = line.strip()
                if not line or line.startswith("Page"):
                    continue
                if not re.match(r'^\d{1,2}/\d{1,2}/\d{4}', line):
                    continue
                amount = extract_amount_from_line(line)
                if amount is None:
                    continue
                amount = normalize_signed_amount(amount, is_debit=True, is_credit=False)
                parts = line.split()
                date_str = parts[0]
                date = normalize_date(date_str)
                desc = " ".join(parts[1:]) if len(parts) > 1 else ""
                key = collision_key(date, desc, amount)
                idx = collision_map.get(key, 0)
                collision_map[key] = idx + 1
                txn = self._make_txn(date, desc, line, amount, idx)
                transactions.append(txn)

        # Process Payments section (credits)
        if payments_header != -1:
            for line in lines[payments_header+1:]:
                line = line.strip()
                if not line or line.startswith("Page") or "TOTAL FOR THIS PERIOD" in line:
                    continue
                if not re.match(r'^\d{1,2}/\d{1,2}/\d{4}', line):
                    continue
                amount = extract_amount_from_line(line)
                if amount is None:
                    continue
                amount = normalize_signed_amount(amount, is_debit=False, is_credit=True)
                parts = line.split()
                date_str = parts[0]
                date = normalize_date(date_str)
                desc = " ".join(parts[1:]) if len(parts) > 1 else ""
                key = collision_key(date, desc, amount)
                idx = collision_map.get(key, 0)
                collision_map[key] = idx + 1
                txn = self._make_txn(date, desc, line, amount, idx)
                transactions.append(txn)

        # Deduplicate (collision map already handled, but safe)
        seen = set()
        unique = []
        for txn in transactions:
            if txn.txn_uid not in seen:
                seen.add(txn.txn_uid)
                unique.append(txn)
        return unique