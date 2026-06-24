import re

def clean_text(text: str) -> str:
    """Normalize text for ML training/prediction."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Remove special characters except spaces and alphanumeric
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text