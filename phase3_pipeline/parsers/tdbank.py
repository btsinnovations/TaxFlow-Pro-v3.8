"""TD Bank statement parser."""
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict

from ..models import Transaction
from .base import (
    BaseParser, normalize_date, normalize_signed_amount,
    generate_stable_uid, collision_key
)
from . import register_parser

@register_parser
class TDBankParser(BaseParser):
    institution_name = "TD Bank"
    priority = 90

    def can_handle(self, text: str) -> bool:
        text_lower = text.lower()
        return "td bank" in text_lower or "tdbusiness" in text_lower

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        year = datetime.now().year
        period_match = re.search(r'StatementPeriod:\s+\w+\d{4}-\w+(\d{4})', text)
        if period_match:
            year = int(period_match.group(1))

        lines = text.splitlines()
        pattern = re.compile(r'^(\d{2}/\d{2})\s+([A-Za-z0-9,]+?)\s+([\d,]+\.\d{2})$')
        collision_map: Dict[tuple, int] = {}

        for line in lines:
            line = line.strip()
            if not line or 'Subtotal:' in line or 'Total' in line:
                continue
            m = pattern.match(line)
            if m:
                date_str = m.group(1)
                desc = m.group(2).replace(',', ' ')
                amount_str = m.group(3).replace(',', '')
                try:
                    raw_amount = Decimal(amount_str)
                except:
                    continue
                is_debit = any(k in desc.upper() for k in ['DEBIT', 'WITHDRAWAL', 'PAYMENT', 'FEE', 'CHARG'])
                amount = normalize_signed_amount(raw_amount, is_debit=is_debit, is_credit=not is_debit)
                date = f"{date_str.replace('/', '-')}-{year}"
                key = collision_key(date, desc, amount)
                idx = collision_map.get(key, 0)
                collision_map[key] = idx + 1
                txn = self._make_txn(date, desc, line, amount, idx)
                transactions.append(txn)
        return transactions