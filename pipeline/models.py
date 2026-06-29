from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict, Any
import json

@dataclass
class Transaction:
    date: str
    description: str          # Normalized payee or cleaned description
    raw_description: str = "" # Original bank text (optional enhancement)
    amount: Decimal = Decimal(0)

    category: Optional[str] = None
    payee: Optional[str] = None
    institution: Optional[str] = None

    txn_uid: str = ""
    parent_txn_uid: Optional[str] = None

    split_flag: bool = False
    split_group_id: Optional[str] = None
    original_amount: Optional[Decimal] = None
    split_reason: Optional[str] = None

    tax_category: str = "uncategorized"
    tax_line: str = ""
    tax_deductible: bool = False

    memo: str = ""

    is_tombstone: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "description": self.description,
            "raw_description": self.raw_description,
            "amount": f"{self.amount:.2f}",
            "category": self.category or "",
            "payee": self.payee or "",
            "institution": self.institution or "",
            "txn_uid": self.txn_uid,
            "parent_txn_uid": self.parent_txn_uid or "",
            "split_flag": self.split_flag,
            "split_group_id": self.split_group_id or "",
            "original_amount": f"{self.original_amount:.2f}" if self.original_amount else "",
            "tax_category": self.tax_category,
            "tax_line": self.tax_line,
            "tax_deductible": self.tax_deductible,
            "memo": self.memo,
            "is_tombstone": self.is_tombstone,
        }