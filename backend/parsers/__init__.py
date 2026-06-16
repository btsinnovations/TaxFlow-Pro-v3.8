"""
Unified PDF parsing package for TaxFlow Pro v3.7.

Provides:
- parse_pdf_to_dict()       API-compatible dict output (used by backend upload router).
- parse_pdf_to_transactions() List[Transaction] style dict output for CLI.
- detect_institution()      Institution detection shared with phase3 pipeline.
- dict_to_backend_model()   Convert parser dicts to backend DB insert kwargs.
- model_to_dict()             Convert backend DB rows to API-compatible dicts.
- deduplicate_dicts()         Deduplicate parsed transaction dicts.
- GenericPDFParser            Legacy backend statement parser class.
"""
from .generic_pdf import GenericPDFParser, parse_pdf_to_dict, parse_pdf_to_transactions, detect_institution
from .institution import INSTITUTION_ALIASES
from .transaction_builder import (
    dict_to_backend_model,
    model_to_dict,
    deduplicate_dicts,
    ensure_tx_type,
)

__all__ = [
    "GenericPDFParser",
    "parse_pdf_to_dict",
    "parse_pdf_to_transactions",
    "detect_institution",
    "INSTITUTION_ALIASES",
    "dict_to_backend_model",
    "model_to_dict",
    "deduplicate_dicts",
    "ensure_tx_type",
]
