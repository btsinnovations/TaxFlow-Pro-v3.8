"""
Merchant alias normalization – shared across identity and pdf_parser.
Prevents circular imports.
"""
from pathlib import Path
from .categorizer import PriorityCategorizer
from .logger import Logger

logger = Logger("alias_utils")
_categorizer = None

def normalize_alias(description: str) -> str:
    """Apply merchant aliases from categories.yaml, return cleaned string."""
    global _categorizer
    if not description:
        return ""
    if _categorizer is None:
        try:
            yaml_path = Path(__file__).parent.parent / "categories.yaml"
            _categorizer = PriorityCategorizer(str(yaml_path))
        except Exception as e:
            logger.warning(f"Unable to load categories.yaml: {e}")
            return description.strip()
    try:
        return _categorizer._apply_aliases(description).strip()
    except Exception:
        return description.strip()