import hashlib
from decimal import Decimal
from typing import Optional
from .alias_utils import normalize_alias

class IdentityService:
    VERSION = "v2"

    @staticmethod
    def generate(date: str, description: str, amount: Decimal, institution: Optional[str], idx: int = 0) -> str:
        # Normalise description and institution
        norm_desc = normalize_alias(description or "")
        norm_desc = norm_desc.upper().strip()
        norm_inst = (institution or "").upper().strip()
        key = f"{IdentityService.VERSION}|{norm_inst}|{date}|{amount}|{norm_desc}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
