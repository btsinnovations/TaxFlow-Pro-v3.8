"""
Date, amount, and transaction ID normalization.
Pre-Phase fixes applied:
  - Deterministic century resolution (no system clock dependency)
  - Exact Decimal arithmetic everywhere
  - Robust European number format support
"""
import re
import hashlib
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CLEAN_PATTERN = re.compile(r"[^\d.\-\(\)]")
EUROPEAN_NUMBER_PATTERN = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
PARENS_PATTERN = re.compile(r"\((.*)\)")


def normalize_date(date_str: str, statement_year: Optional[int] = None) -> str:
    """Parse date with deterministic century resolution based on statement_year."""
    if not date_str or not str(date_str).strip():
        raise ValueError("Empty date string provided")

    cleaned = str(date_str).strip().replace("\\", "/").replace("-", "/").strip()

    # Preferred: dateutil
    try:
        from dateutil import parser
        dt = parser.parse(cleaned, fuzzy=True, yearfirst=False)

        if statement_year and dt.year < 100:
            base_century = (statement_year // 100) * 100
            candidate = base_century + dt.year
            if candidate > statement_year + 5:          # Agreed tolerance
                candidate -= 100
            dt = dt.replace(year=candidate)

        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Manual numeric fallback
    parts = cleaned.split("/")
    if len(parts) == 3:
        try:
            if len(parts[0]) == 4:  # YYYY/MM/DD
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"

            month = int(parts[0])
            day = int(parts[1])
            year = int(parts[2])

            if year < 100 and statement_year:
                base_century = (statement_year // 100) * 100
                candidate = base_century + year
                if candidate > statement_year + 5:
                    candidate -= 100
                year = candidate
            elif year < 100:
                year += 2000

            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            pass

    # Month name fallback
    lower = cleaned.lower()
    for m_name, m_num in MONTHS.items():
        if m_name in lower:
            digits = re.findall(r"\d+", cleaned)
            if digits:
                day = int(digits[0])
                year = int(digits[-1]) if len(digits) > 1 else (statement_year or 2000)
                if year < 100 and statement_year:
                    base_century = (statement_year // 100) * 100
                    candidate = base_century + year
                    if candidate > statement_year + 5:
                        candidate -= 100
                    year = candidate
                return f"{year:04d}-{m_num:02d}-{day:02d}"

    raise ValueError(f"Unable to parse date: '{date_str}' (statement_year={statement_year})")


def normalize_amount(amount_str: str) -> Decimal:
    """Convert currency string to exact Decimal."""
    if not amount_str or not str(amount_str).strip():
        raise ValueError(f"Empty amount string: '{amount_str}'")

    cleaned = str(amount_str).strip()

    # European format (1.234,56)
    if EUROPEAN_NUMBER_PATTERN.search(cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    cleaned = CLEAN_PATTERN.sub("", cleaned)

    # Parentheses = negative
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]

    try:
        val = Decimal(cleaned)
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"Invalid amount format: '{amount_str}'") from None


def generate_transaction_id(date_str: str, description: str, amount: Decimal) -> str:
    """Stable hash using exact Decimal representation."""
    canonical = f"{date_str}||{description.strip()}||{amount:.2f}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
