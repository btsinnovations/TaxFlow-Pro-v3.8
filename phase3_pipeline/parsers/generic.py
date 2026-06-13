"""Generic fallback parsers."""
import re
from typing import List, Dict

from ..models import Transaction
from ..normalization import normalize_amount
from .base import (
    BaseParser, normalize_date, normalize_signed_amount,
    extract_amount_from_line, generate_stable_uid, collision_key
)
from . import register_parser

@register_parser
class AdvancedGenericParser(BaseParser):
    institution_name = "unknown"
    priority = 20

    def can_handle(self, text: str) -> bool:
        return True

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        lines = text.splitlines()
        collision_map: Dict[tuple, int] = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            date_match = re.match(r'^(\d{1,2}/\d{1,2}/\d{2,4})\s+(.*)', line)
            if not date_match:
                continue
            date_str = date_match.group(1)
            remaining = date_match.group(2)
            amount = extract_amount_from_line(remaining)
            if amount is None:
                continue
            is_credit = bool(re.search(r'\bCR\b', line, re.IGNORECASE))
            is_debit = bool(re.search(r'\bDR\b', line, re.IGNORECASE))
            amount = normalize_signed_amount(amount, is_debit=is_debit, is_credit=is_credit)
            desc = re.sub(r'\s*[-$]?\d[\d,]*\.\d{2}\s*$', '', remaining).strip()
            date = normalize_date(date_str)
            key = collision_key(date, desc, amount)
            idx = collision_map.get(key, 0)
            collision_map[key] = idx + 1
            txn = self._make_txn(date, desc, line, amount, idx)
            transactions.append(txn)
        return transactions

@register_parser
class GenericParser(BaseParser):
    institution_name = "unknown"
    priority = 10

    def can_handle(self, text: str) -> bool:
        return True

    def parse(self, text: str) -> List[Transaction]:
        transactions = []
        lines = text.splitlines()
        patterns = [
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+(.*?)\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d_{1,2}/\d_{1,2}/\d_{2,4})\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)\s+(.*)',
            r'(\d_{1,2}/\d_{1,2}/\d_{2,4})\s+Withdrawal.*?\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)\s+(.*)',
            r'(\d_{1,2}/\d_{1,2}/\d_{2,4})\s+Deposit.*?\s+([-\$]?\d+(?:,\d{3})*(?:\.\d{2})?)\s+(.*)',
        ]
        collision_map: Dict[tuple, int] = {}
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            matched = False
            for pat in patterns:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    groups = m.groups()
                    date_str = groups[0]
                    date = normalize_date(date_str)
                    amount_str = None
                    desc = None
                    for g in groups[1:]:
                        if re.search(r'[\$\-]?\d+(?:,\d{3})*(?:\.\d{2})?', g):
                            amount_str = g
                        elif len(g) > 2:
                            desc = g
                    if amount_str and desc:
                        raw_amount = normalize_amount(amount_str)
                        if raw_amount is not None:
                            amount = normalize_signed_amount(raw_amount, is_debit=(raw_amount < 0), is_credit=(raw_amount > 0))
                            key = collision_key(date, desc, amount)
                            idx = collision_map.get(key, 0)
                            collision_map[key] = idx + 1
                            txn = self._make_txn(date, desc, line, amount, idx)
                            transactions.append(txn)
                            matched = True
                            break
        return transactions