"""Educational Federal Credit Union parser (checking and credit)."""
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict

from ..models import Transaction
from .base import (
    BaseParser, normalize_date, normalize_signed_amount,
    generate_stable_uid, extract_amount_from_line, collision_key
)
from . import register_parser

@register_parser
class EdFedParser(BaseParser):
    institution_name = "EdFed"
    priority = 90

    def can_handle(self, text: str) -> bool:
        return ("educational federal" in text.lower() or "edfed" in text.lower()) and "share draft" in text.lower()

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        lines = text.splitlines()
        year = datetime.now().year
        year_match = re.search(r'([A-Za-z]+)\s+(\d{4})', text[:200])
        if year_match:
            year = int(year_match.group(2))

        in_activity = False
        i = 0
        collision_map: Dict[tuple, int] = {}

        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if not line:
                continue
            if "ACCOUNT ACTIVITY FOR SHARE DRAFT" in line:
                in_activity = True
                continue
            if not in_activity:
                continue

            date_match = re.match(r'^(\d{2}/\d{2}/\d{4})\s+(.*)', line)
            if not date_match:
                continue

            date_str = date_match.group(1)
            date = normalize_date(date_str)
            rest = date_match.group(2)

            amount = None
            desc_part = rest
            amount_match = re.search(r'(-?\d+(?:,\d{3})*\.\d{2})\s+(\d+(?:,\d{3})*\.\d{2})$', rest)
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '')
                try:
                    raw_amount = Decimal(amount_str)
                    amount = raw_amount
                except:
                    pass
                desc_part = rest[:amount_match.start()].strip()
            else:
                raw_amount = extract_amount_from_line(rest)
                if raw_amount is not None:
                    amount = raw_amount

            # Merge subsequent lines (merchant name)
            full_desc = desc_part
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                if re.match(r'^\d{2}/\d{2}/\d{4}', next_line):
                    break
                if next_line.startswith(("TYPE:", "ID:", "CO:", "IMPORTANT", "Telephone", "Page", "ACCOUNT ACTIVITY", "SUMMARY")):
                    break
                if "Date Posted" in next_line:
                    break
                full_desc += " " + next_line
                i += 1

            if amount is None:
                amount = extract_amount_from_line(full_desc)
                if amount is None:
                    continue

            is_debit = any(k in full_desc for k in ["Withdrawal", "Debit", "Transfer To", "Fee"])
            amount = normalize_signed_amount(amount, is_debit=is_debit, is_credit=not is_debit)

            key = collision_key(date, full_desc, amount)
            idx = collision_map.get(key, 0)
            collision_map[key] = idx + 1
            txn = self._make_txn(date, full_desc, line, amount, idx)
            transactions.append(txn)

        return transactions


@register_parser
class EdFedCreditParser(BaseParser):
    institution_name = "EdFed Credit"
    priority = 90

    def can_handle(self, text: str) -> bool:
        return "rewards visa" in text.lower() or "credit card statement" in text.lower()

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        lines = text.splitlines()
        date_pattern = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+(.*)')
        current_desc = []
        current_txn = None
        collision_map: Dict[tuple, int] = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(skip in line for skip in ["TRANSACTIONS", "SUMMARY", "Payment", "Page", "Member", "Account", "Rewards", "VISA", "Credit Limit", "Minimum Payment"]):
                continue

            match = date_pattern.match(line)
            if match:
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

                date_str = match.group(1)
                date = normalize_date(date_str)
                rest = match.group(2)
                amount_match = re.search(r'([+-]?\$?\d+(?:,\d{3})*\.\d{2})$', rest)
                if not amount_match:
                    continue
                amount_str = amount_match.group(1)
                desc_part = rest[:amount_match.start()].strip()
                amount_clean = amount_str.replace('$', '').replace(',', '')
                try:
                    raw_amount = Decimal(amount_clean)
                except:
                    continue
                is_debit = amount_str.startswith('-') or ("purchase" in desc_part.lower())
                amount = normalize_signed_amount(raw_amount, is_debit=is_debit, is_credit=not is_debit)

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