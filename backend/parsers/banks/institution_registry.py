"""Institution detection registry for B8 Phase 2 family-based parsing.

This module augments backend/parsers/institution.py by mapping the DocuClipper
institution list (and any future scraped registry) to layout-family parsers.
It is imported by the dispatch layer and used as a fallback when no dedicated
Phase 1 parser matches.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.parsers.banks.families import (
    BrokeragePdfFamily,
    CreditCardPdfFamily,
    CsvStandardFamily,
    OfxQfxFamily,
    PdfTableMultiFamily,
    PdfTableSimpleFamily,
)


_FAMILY_CLASSES = {
    "csv_standard": CsvStandardFamily,
    "ofx_qfx": OfxQfxFamily,
    "pdf_table_simple": PdfTableSimpleFamily,
    "pdf_table_multi": PdfTableMultiFamily,
    "credit_card_pdf": CreditCardPdfFamily,
    "brokerage_pdf": BrokeragePdfFamily,
}

_FAMILY_BY_CONTENT_KEYWORD: Dict[str, List[str]] = {
    "ofx_qfx": ["OFXHEADER:", "<STMTTRN>", "<SIGNONMSGSRSV1>", "<BANKMSGSRSV1>", "<CCMSGSRSV1>"],
    "csv_standard": ["Date,Description,Amount", "Transaction Date,Description,Amount", "Posted Date,Description,Amount"],
    "pdf_table_multi": ["Page 1 of", "Page 2 of", "Continued on next page"],
    "credit_card_pdf": ["Cardmember", "American Express", "payment - thank you", "interest charge"],
    "brokerage_pdf": ["Brokerage Statement", "Holdings", "Cash Transactions", "Dividend Received"],
}

_FAMILY_BY_FILENAME_KEYWORD: Dict[str, str] = {
    "chase": "ofx_qfx",
    "ofx": "ofx_qfx",
    "qfx": "ofx_qfx",
    "csv": "csv_standard",
    "amex": "credit_card_pdf",
    "americanexpress": "credit_card_pdf",
    "creditcard": "credit_card_pdf",
    "hsbc": "pdf_table_multi",
    "schwab": "brokerage_pdf",
    "brokerage": "brokerage_pdf",
    "fidelity": "brokerage_pdf",
    "tdameritrade": "brokerage_pdf",
    "etrade": "brokerage_pdf",
}


class InstitutionFamilyRegistry:
    """Load and query the DocuClipper institution registry."""

    def __init__(self, registry_path: Optional[Path] = None) -> None:
        self.registry_path = registry_path or self._default_registry_path()
        self._data: Optional[Dict[str, Any]] = None
        self._by_name: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _default_registry_path() -> Path:
        return Path(__file__).resolve().parents[3] / "data" / "docuclipper-institutions.json"

    def _load(self) -> None:
        if self._data is not None:
            return
        if not self.registry_path.exists():
            self._data = {"institutions": [], "phase1_institutions": []}
            return
        with self.registry_path.open("r", encoding="utf-8") as f:
            self._data = json.load(f)
        for entry in self._data.get("institutions", []):
            norm = self._normalize(entry["name"])
            self._by_name[norm] = entry
            # Add family metadata from family name
            entry.setdefault("parser_family", entry.get("family"))

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def lookup(self, name: str) -> Optional[Dict[str, Any]]:
        self._load()
        return self._by_name.get(self._normalize(name))

    def detect_family(self, content: bytes, filename: Optional[str] = None) -> Tuple[str, float, Optional[str]]:
        """Return (family_name, confidence, institution_name).

        Confidence scale:
          0.90 = exact filename/institution match in registry
          0.80 = content keyword match (OFX/CSV header / family markers)
          0.60 = filename extension/family keyword match
          0.50 = inferred from filename substring in registry
          0.30 = generic PDF fallback
        """
        self._load()

        # Content-level format detection
        text = content[:4096].decode("utf-8", errors="replace")
        for family, keywords in _FAMILY_BY_CONTENT_KEYWORD.items():
            if any(kw.lower() in text.lower() for kw in keywords):
                return family, 0.80, None

        # Filename extension / family keyword heuristic
        if filename:
            lowered = filename.lower()
            for keyword, family in _FAMILY_BY_FILENAME_KEYWORD.items():
                if keyword in lowered:
                    return family, 0.60, None

        # Filename heuristic against registry institution names
        if filename:
            lowered = filename.lower()
            for entry in self._data.get("institutions", []):
                if self._normalize(entry["name"]) in lowered:
                    return entry["family"], 0.50, entry["name"]

        # Default to PDF simple
        return "pdf_table_simple", 0.30, None

    def get_parser(self, family: str, institution: Optional[str] = None):
        cls = _FAMILY_CLASSES.get(family)
        if not cls:
            return None
        return cls(institution or family.replace("_", " ").title())

    def all_institutions(self) -> List[Dict[str, Any]]:
        self._load()
        return list(self._data.get("institutions", []))


def detect_institution_family(
    content: bytes,
    filename: Optional[str] = None,
    registry: Optional[InstitutionFamilyRegistry] = None,
) -> Dict[str, Any]:
    """High-level detection returning a dispatch-ready dict."""
    reg = registry or InstitutionFamilyRegistry()
    family, confidence, institution = reg.detect_family(content, filename=filename)
    parser = reg.get_parser(family, institution)
    return {
        "family": family,
        "confidence": confidence,
        "institution": institution,
        "parser": parser,
        "needs_review": confidence < 0.80,
    }
