import hashlib
<<<<<<< HEAD
=======
import re
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
from decimal import Decimal
from typing import Optional
from .alias_utils import normalize_alias

class IdentityService:
    VERSION = "v2"

    @staticmethod
<<<<<<< HEAD
    def generate(date: str, description: str, amount: Decimal, institution: Optional[str], idx: int = 0) -> str:
        # Normalise description and institution
        norm_desc = normalize_alias(description or "")
        norm_desc = norm_desc.upper().strip()
        norm_inst = (institution or "").upper().strip()
        key = f"{IdentityService.VERSION}|{norm_inst}|{date}|{amount}|{norm_desc}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
=======
    def generate(date: str, description: str, amount, institution: Optional[str], idx: int = 0) -> str:
        # Normalise description and institution
        norm_desc = normalize_alias(description or "")
        # Strip non-alphanumeric characters and collapse whitespace so variants
        # like "WAL-MART #123" and "Walmart" converge to the same canonical ID.
        norm_desc = re.sub(r"[^A-Z0-9]", " ", norm_desc.upper())
        norm_desc = re.sub(r"\s+", " ", norm_desc).strip()
        norm_inst = (institution or "").upper().strip()
        key = f"{IdentityService.VERSION}|{norm_inst}|{date}|{amount}|{norm_desc}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_stable(date: str, description: str, amount, institution: Optional[str]) -> str:
        """Backward-compatible alias for generate without an index."""
        return IdentityService.generate(date, description, amount, institution, idx=0)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
