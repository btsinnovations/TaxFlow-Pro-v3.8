"""Institution detection for bank statement PDFs."""


def detect_institution(text: str) -> str:
    """Detect financial institution from raw PDF text."""
    text_lower = text.lower()
    if "share draft" in text_lower or "educational federal" in text_lower:
        return "EdFed"
    if "cash app" in text_lower and any(
        m in text_lower for m in ["to ", "from ", "cash app payment", "cash app card"]
    ):
        return "Cash App"
    if "chime" in text_lower:
        return "Chime"
    if "td bank" in text_lower or "tdbusiness" in text_lower:
        return "TD Bank"
    if "bank of america" in text_lower:
        return "Bank of America"
    if "chase" in text_lower:
        return "Chase"
    if "wells fargo" in text_lower:
        return "Wells Fargo"
    return "unknown"


INSTITUTION_ALIASES = {
    "EdFed": ["Educational Federal Credit Union", "EdFed CU"],
    "Cash App": ["CashApp", "Square Cash"],
    "TD Bank": ["TDBusiness"],
}
