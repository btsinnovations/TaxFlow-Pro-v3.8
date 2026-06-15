# text_utils.py
import re

def clean_text(text: str) -> str:
    """
    Preprocess a raw transaction description.
    Must remain identical for training and prediction.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # Remove bracketed codes like [1234]
    text = re.sub(r'\[.*?\]', ' ', text)
    # Remove dates (2026-05-01, 05/01/2026, etc.)
    text = re.sub(r'\b\d{2,4}[-/]\d{2,4}[-/]\d{2,4}\b', ' ', text)
    # Keep only letters, digits and whitespace
    text = re.sub(r'[^\w\s]', ' ', text)
    # Collapse multiple spaces
    return " ".join(text.split())
