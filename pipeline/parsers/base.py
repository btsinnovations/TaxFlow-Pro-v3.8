"""Base classes and shared utilities for all parsers."""
import re
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ..models import Transaction
from ..identity import IdentityService
from ..alias_utils import normalize_alias

# ----------------------------------------------------------------------
# Date & amount helpers
# ----------------------------------------------------------------------
def normalize_date(date_str: str) -> str:
    """Convert MM/DD/YYYY or MM/DD/YY to MM-DD-YYYY."""
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%m-%d-%Y")
        except ValueError:
            continue
    return date_str.replace('/', '-')

def extract_amount_from_line(line: str) -> Optional[Decimal]:
    """Extract and normalize amount from a line (supports $, commas, parentheses)."""
    match = re.search(r'(-?\$?\d+(?:,\d{3})*\.\d{2})', line)
    if not match:
        return None
    amount_str = match.group(1)
    if amount_str.startswith('(') and amount_str.endswith(')'):
        amount_str = '-' + amount_str[1:-1]
    amount_clean = amount_str.replace('$', '').replace(',', '')
    try:
        return Decimal(amount_clean)
    except:
        return None

def normalize_signed_amount(
    amount: Decimal,
    *,
    is_debit: bool = False,
    is_credit: bool = False,
) -> Decimal:
    """Single authority for financial sign normalization."""
    if is_credit and not is_debit:
        return abs(amount)
    if is_debit and not is_credit:
        return -abs(amount)
    return amount

def generate_stable_uid(date: str, description: str, amount: Decimal, institution: str) -> str:
    return IdentityService.generate_stable(date, description, amount, institution)

def collision_key(date: str, description: str, amount: Decimal) -> tuple:
    """Normalised key for duplicate detection within a statement."""
    return (date, normalize_alias(description).upper().strip(), amount)

# ----------------------------------------------------------------------
# Base Parser
# ----------------------------------------------------------------------
class BaseParser(ABC):
    institution_name: str = "unknown"
    priority: int = 0

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "institution_name"):
            cls.institution_name = "unknown"
        if not hasattr(cls, "priority"):
            cls.priority = 0

    @abstractmethod
    def can_handle(self, text: str) -> bool:
        pass

    @abstractmethod
    def parse(self, text: str) -> List[Transaction]:
        pass

    def _make_txn(
        self,
        date: str,
        description: str,
        raw_line: str,
        amount: Decimal,
        collision_index: int = 0,
    ) -> Transaction:
        unique_desc = f"{description}|{collision_index}" if collision_index > 0 else description
        payee = normalize_alias(description)
        return Transaction(
            date=date,
            description=description,
            raw_description=raw_line,
            amount=amount,
            category=None,
            payee=payee,
            institution=self.institution_name,
            txn_uid=generate_stable_uid(date, unique_desc, amount, self.institution_name),
        )