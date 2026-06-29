#!/usr/bin/env python3
"""
PDF Parser for Financial ETL Pipeline.

This module is now a thin backward-compatible wrapper around the unified
backend/parsers package. The canonical parsing logic lives in
backend/parsers.generic_pdf (GenericPDFParser) and the phase3
phase3_pipeline/parsers plugin registry.
"""
from typing import List, Tuple
from pathlib import Path

from .models import Transaction
from .ocr import extract_text_from_pdf
from .config import OCR_CONFIG
import sys
from pathlib import Path

# Allow imports from the project root so backend.parsers is reachable.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.parsers import (
    parse_pdf_to_dict,
    parse_pdf_to_transactions,
    detect_institution,
)
from .parsers import get_parser


# Re-export institution detection so downstream callers keep working.
__all__ = [
    "pdf_to_transactions",
    "detect_institution",
]


def pdf_to_transactions(pdf_path: Path, profile: str = "personal") -> Tuple[List[Transaction], str]:
    """Backward-compatible pipeline entry point."""
    if not pdf_path.exists():
        return [], ""

    prefer_digital = OCR_CONFIG.get("prefer_digital", True)
    raw_text = extract_text_from_pdf(pdf_path, prefer_digital=prefer_digital)
    if not raw_text:
        return [], ""

    institution = detect_institution(raw_text)

    # Special case: EdFed credit card is not covered by the plugin registry
    # but the unified generic parser may still find transactions.
    if "REWARDS VISA" in raw_text or "Credit Card Statement" in raw_text:
        institution = "EdFed Credit"

    # Try the phase3 plugin parser registry first for institution-specific logic.
    parser = get_parser(raw_text)
    parsed_institution = getattr(parser, "institution_name", institution)
    plugin_transactions = parser.parse(raw_text)

    # If the plugin registry returned nothing, fall back to the unified backend parser.
    if not plugin_transactions:
        tx_dicts = parse_pdf_to_transactions(pdf_path, institution=institution)
        plugin_transactions = [
            Transaction(
                date=tx.get("date", ""),
                description=tx.get("description", ""),
                raw_description=tx.get("description", ""),
                amount=tx.get("amount") or 0,
                category=None,
                payee=tx.get("description", "")[:80],
                institution=institution or parsed_institution,
                txn_uid="",
            )
            for tx in tx_dicts
        ]

    # Ensure every transaction has a stable uid.
    for idx, txn in enumerate(plugin_transactions):
        if not txn.txn_uid:
            from .identity import IdentityService
            txn.txn_uid = IdentityService.generate(
                txn.date, txn.description, txn.amount, txn.institution, idx
            )

    # Deduplicate by txn_uid.
    seen = set()
    unique = []
    for txn in plugin_transactions:
        if txn.txn_uid not in seen:
            seen.add(txn.txn_uid)
            unique.append(txn)

    return unique, raw_text
