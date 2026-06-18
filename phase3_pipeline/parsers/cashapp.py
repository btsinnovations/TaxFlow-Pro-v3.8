"""Cash App statement parser."""
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
class CashAppParser(BaseParser):
    institution_name = "Cash App"
    priority = 100

    def can_handle(self, text: str) -> bool:
        text_lower = text.lower()
        # Require genuine Cash App statement markers, not merely "Cash App"
        # mentions inside another bank's transaction descriptions.
        is_cash_app_statement = any(
            m in text_lower
            for m in [
                "cash app investing",
                "cash app bank",
                "cash app taxes",
                "square cash",
                "statement period",
                "beginning balance",
            ]
        )
        return "cash app" in text_lower and is_cash_app_statement and any(
            m in text_lower for m in ["to ", "from ", "cash app payment", "cash app card"]
        )

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        lines = text.splitlines()
        year = datetime.now().year
        year_match = re.search(r'([A-Za-z]+)\s+(\d{4})', text)
        if year_match:
            year = int(year_match.group(2))

        current_desc = []
        current_txn = None
        collision_map: Dict[tuple, int] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue
            date_match = re.match(r'^([A-Za-z]{3}\s+\d{1,2})\s+(.*)', line)
            if date_match:
                if current_txn:
                    full_desc = " ".join(current_desc).strip()
                    if full_desc:
                        current_txn.description = full_desc
                        current_txn.raw_description = full_desc
                        key = collision_key(current_txn.date, full_desc, current_txn.amount)
                        idx = collision_map.get(key, 0)
                        collision_map[key] = idx + 1
                        current_txn.txn_uid = generate_stable_uid(
                            current_txn.date, f"{full_desc}|{idx}", current_txn.amount, self.institution_name
                        )
                        transactions.append(current_txn)

                date_str = date_match.group(1)
                rest = date_match.group(2)
                try:
                    date_obj = datetime.strptime(f"{date_str} {year}", "%b %d %Y")
                    date = date_obj.strftime("%m-%d-%Y")
                except:
                    date = date_str

                amount_match = re.search(r'\$0\.00\s+(.*?)$', rest)
                if amount_match:
                    amount_str = amount_match.group(1).strip()
                    desc_part = rest[:amount_match.start()].strip()
                else:
                    parts = rest.split()
                    if not parts:
                        continue
                    amount_str = parts[-1]
                    desc_part = " ".join(parts[:-1])

                amount_str = amount_str.replace(',', '')
                if amount_str.startswith('+'):
                    sign = 1
                    amount_str = amount_str[1:].strip()
                else:
                    sign = -1
                numeric_match = re.search(r'(\d+(?:\.\d{2})?)', amount_str)
                if not numeric_match:
                    continue
                raw_amount = Decimal(numeric_match.group(1))
                amount = normalize_signed_amount(raw_amount, is_credit=(sign == 1), is_debit=(sign == -1))

                current_txn = Transaction(
                    date=date,
                    description="",
                    raw_description="",
                    amount=amount,
                    category=None,
                    payee=None,
                    institution=self.institution_name,
                    txn_uid="",
                )
                current_desc = [desc_part]
            else:
                if current_txn:
                    current_desc.append(line)

        if current_txn:
            full_desc = " ".join(current_desc).strip()
            if full_desc:
                current_txn.description = full_desc
                current_txn.raw_description = full_desc
                key = collision_key(current_txn.date, full_desc, current_txn.amount)
                idx = collision_map.get(key, 0)
                collision_map[key] = idx + 1
                current_txn.txn_uid = generate_stable_uid(
                    current_txn.date, f"{full_desc}|{idx}", current_txn.amount, self.institution_name
                )
                transactions.append(current_txn)

        return transactions