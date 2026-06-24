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
from .ocr_parser import OCRPDFParser, parse_pdf_to_cr_dict
from .institution import INSTITUTION_ALIASES, detect_institution_with_columns, parse_statement_pdf
from .transaction_builder import (
    dict_to_backend_model,
    model_to_dict,
    deduplicate_dicts,
    ensure_tx_type,
)
from .tdbank import TDBankParser, parse_td_bank_pdf
from .chime import ChimeParser, parse_chime_pdf
from .edfed import EdFedParser, parse_edfed_pdf
from .queensborough import QueensboroughParser, parse_queensborough_pdf

__all__ = [
    "GenericPDFParser",
    "OCRPDFParser",
    "TDBankParser",
    "ChimeParser",
    "EdFedParser",
    "QueensboroughParser",
    "parse_pdf_to_dict",
    "parse_pdf_to_transactions",
    "parse_pdf_to_cr_dict",
    "parse_statement_pdf",
    "parse_td_bank_pdf",
    "parse_chime_pdf",
    "parse_edfed_pdf",
    "parse_queensborough_pdf",
    "detect_institution",
    "detect_institution_with_columns",
    "INSTITUTION_ALIASES",
    "dict_to_backend_model",
    "model_to_dict",
    "deduplicate_dicts",
    "ensure_tx_type",
]
