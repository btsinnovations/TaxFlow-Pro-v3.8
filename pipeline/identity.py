import hashlib
import re
from decimal import Decimal
from typing import Optional
from .alias_utils import normalize_alias

class IdentityService:
    VERSION = "v2"
    TXN_VERSION = "v3"

    @staticmethod
    def _canonicalize_description(description: str) -> str:
        """Return a stable, case-insensitive, punctuation-normalized token."""
        norm_desc = normalize_alias(description or "")
        # Collapse store/location identifiers so variants like "WAL-MART #123"
        # and "Walmart 1234" converge to the same canonical ID.
        norm_desc = re.sub(r"[^A-Z0-9]", " ", norm_desc.upper())
        norm_desc = re.sub(r"\s+", " ", norm_desc).strip()
        return norm_desc

    @staticmethod
    def _canonicalize_amount(amount) -> str:
        """Return a two-decimal string for any numeric/str amount."""
        if amount is None:
            return ""
        try:
            if isinstance(amount, Decimal):
                return f"{amount:.2f}"
            if isinstance(amount, (int, float)):
                return f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"
            # Strip currency symbols, commas, and whitespace for strings.
            s = re.sub(r"[,\s$]", "", str(amount))
            return f"{Decimal(s).quantize(Decimal('0.01'))}"
        except Exception:
            return str(amount).strip()

    @staticmethod
    def generate(date: str, description: str, amount, institution: Optional[str], idx: int = 0) -> str:
        norm_desc = IdentityService._canonicalize_description(description)
        norm_inst = (institution or "").upper().strip()
        key = f"{IdentityService.VERSION}|{norm_inst}|{date}|{amount}|{norm_desc}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_stable(date: str, description: str, amount, institution: Optional[str]) -> str:
        """Backward-compatible alias for generate without an index."""
        return IdentityService.generate(date, description, amount, institution, idx=0)

    @staticmethod
    def generate_transaction_uid(
        date: str,
        description: str,
        amount,
        institution: Optional[str] = None,
        account: Optional[str] = None,
    ) -> str:
        """Deterministic transaction UID for idempotent imports.

        Formula: SHA-256(version | institution | account | date | amount | normalized_description)
        """
        norm_inst = (institution or "").upper().strip()
        norm_acct = (account or "").upper().strip()
        norm_date = str(date).strip() if date else ""
        norm_amount = IdentityService._canonicalize_amount(amount)
        norm_desc = IdentityService._canonicalize_description(description)
        key = f"{IdentityService.TXN_VERSION}|{norm_inst}|{norm_acct}|{norm_date}|{norm_amount}|{norm_desc}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()
