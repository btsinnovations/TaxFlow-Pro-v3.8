"""Institution detection for bank statement PDFs.

This module embeds the findings from Stage 1 research (STAGE1-RESEARCH.md).
Each institution profile includes detection strings, expected column patterns,
observed quirks, and source notes. No live credentials or real statements are
used; synthetic fixtures exercise the detection layer.

Tier 1 institutions added in v3.9:
- Navy Federal Credit Union
- U.S. Bank
- Citibank
- PNC Bank
- Ally Bank
- SoFi
- Truist
- Discover Bank
- Marcus by Goldman Sachs
- BECU (Boeing Employees Credit Union)

Out of scope / dropped in v3.9:
- None — BECU added post-Stage 2 as the final Tier 1 institution.

Open questions tracked inline below.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from backend.local.guards import validate_pdf_safety


# Detection entries: (canonical_name, [detection_strings], [column_pattern_keywords], {notes})
_INSTITUTION_REGISTRY: List[Tuple[str, List[str], List[str], Dict[str, str]]] = [
    ("TD Bank", ["td bank", "tdbusiness", "td bank credit", "td cash", "td first class", "td business credit", "tdbank"], ["description", "withdrawals", "deposits"], {
        "source": "v3.7 existing parser",
        "quirk": "Checking parser expects MM/DD DESCRIPTION AMOUNT; credit layouts added in P1.1.",
    }),
    ("Bank of America", ["bank of america", "bofa"], ["description", "withdrawal", "deposit"], {
        "source": "v3.7 existing parser",
        "quirk": "Multi-column statements; generic parser fallback common.",
    }),
    ("Chase", ["chase"], ["description", "withdrawals", "deposits", "balance"], {
        "source": "v3.7 existing parser",
        "quirk": "Very common; checking + credit card layouts differ by card product.",
    }),
    ("Chime", ["chime", "chime checking", "spending account", "credit builder"], ["credit builder", "spotme", "savings"], {
        "source": "v3.7 existing parser",
        "quirk": "Neobank; Credit Builder layout differs from checking. Detection broad.",
    }),
    ("EdFed", ["share draft", "educational federal", "edfed rewards visa", "edfed credit card", "educational federal credit union credit"], ["share draft", "transaction date"], {
        "source": "v3.7 existing parser",
        "quirk": "Credit-union share-draft statements; credit parser added in P1.1.",
    }),
    ("Queensborough National Bank", ["queensborough national bank", "queensborough bank & trust", "queensborough bank and trust", "qnb"], ["date", "description", "debit", "credit", "balance"], {
        "source": "P1.1 parser coverage expansion",
        "quirk": "Small regional bank; statements typically Date/Description/Amount.",
    }),
    ("Wells Fargo", ["wells fargo"], ["description", "debits", "credits", "balance"], {
        "source": "v3.7 existing parser",
        "quirk": "Checking/savings/credit card; debit/credit column orientation varies.",
    }),
    ("Cash App", ["cash app", "cashapp"], ["to ", "from ", "cash app payment", "cash app card"], {
        "source": "v3.7 existing parser",
        "quirk": "Peer-to-peer / digital wallet; often single-column amount with To/From semantics.",
    }),
    # Tier 1 additions per v3.9 Stage 1 research
    ("Navy Federal", ["navy federal", "navyfcu", "navy", "fcu"], ["transaction", "withdrawal", "deposit", "balance"], {
        "source": "Stage 1 research — aggregator-inferred from DocuClipper/CapyParse blogs",
        "quirk": "Credit-union statements often list running balance on each transaction row.",
    }),
    ("U.S. Bank", ["u.s. bank", "us bank", "usbank"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — https://www.usbank.com/bank-accounts/checking-accounts/checking-customer-resources/quicken.html",
        "quirk": "Quicken/QuickBooks export docs imply Date/Description/Debit/Credit/Balance columns.",
    }),
    ("Citibank", ["citibank", "citi"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — converter-site inference; no validated public sample PDF acquired",
        "quirk": "OPEN QUESTION: checking vs credit card layout ambiguity. v3.9 assumes multi-column Date/Description/Debit/Credit/Balance pending primary-source fixture.",
    }),
    ("PNC Bank", ["pnc bank", "pncbank", "pnc"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — converter-site inference; no validated public sample PDF acquired",
        "quirk": "OPEN QUESTION: Virtual Wallet vs standard checking statement layouts differ. v3.9 detection only; full parser deferred until sample available.",
    }),
    ("Ally Bank", ["ally bank", "ally"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — aggregator-inferred from online-bank statement guides",
        "quirk": "Online-only bank; statements typically simple Date/Description/Debit/Credit/Balance.",
    }),
    ("SoFi", ["sofi"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — aggregator-inferred from DocuClipper/CapyParse blogs",
        "quirk": "Neobank; SoFi Money statements often single-account, multi-column.",
    }),
    ("Truist", ["truist"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — aggregator-inferred from converter blogs",
        "quirk": "Post-merger brand; statements may still carry legacy BB&T/SunTrust markers.",
    }),
    # BECU added post-Stage 2; primary source sample is a membership application, so columns are inferred.
    ("BECU", ["becu", "boeing employees credit union", "member share savings", "member advantage"], ["transaction date", "description", "withdrawal", "deposit", "balance"], {
        "source": "Primary source sample PDF: https://www.becu.org/-/media/Files/PDF/P-6803.pdf (membership application)",
        "quirk": "OPEN QUESTION: sample PDF is a membership application, not a statement. Column patterns inferred from typical credit-union share-draft statements. A redacted BECU account statement is needed for exact reconciliation-level parsing.",
    }),
    ("Discover Bank", ["discover bank", "discover"], ["description", "purchase", "payment", "balance"], {
        "source": "Stage 1 research — aggregator-inferred",
        "quirk": "Credit-card-first brand; Discover Bank checking/savings use 'purchase'/'payment' terminology.",
    }),
    ("Marcus by Goldman Sachs", ["marcus by goldman sachs", "marcus", "goldman sachs bank"], ["description", "debit", "credit", "balance"], {
        "source": "Stage 1 research — aggregator-inferred from high-yield savings statement guides",
        "quirk": "High-yield savings statements are sparse; detection triggers on 'Marcus' or full brand string.",
    }),
    # Tier 2 additions per v3.11.6 research expansion
    ("American Express", ["american express", "amex", "amex blue", "amex gold", "amex platinum"], ["description", "purchase", "payment", "balance"], {
        "source": "Tier 2 research — 403/blocked sources; layout inferred from credit card statement patterns",
        "quirk": "Credit-card-first; uses 'purchase'/'payment' terminology. Conservative parsing.",
    }),
    ("USAA", ["usaa", "usaa bank", "usaa federal savings"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — military-focused bank; sources limited",
        "quirk": "Conservative parsing; may raise ParserError for ambiguous layouts.",
    }),
    ("PenFed", ["penfed", "pentagon federal", "pentagon federal credit union"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — credit union layout",
        "quirk": "Credit union share-draft patterns; conservative parsing.",
    }),
    ("Alliant Credit Union", ["alliant", "alliant credit union"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — online credit union",
        "quirk": "Online credit union; simpler layout expected.",
    }),
    ("Synchrony Bank", ["synchrony", "synchrony bank"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — online savings / co-branded credit cards",
        "quirk": "May have co-branded credit card layouts; conservative parsing.",
    }),
    ("Huntington Bank", ["huntington", "huntington bank", "huntington national bank"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — regional Midwest bank",
        "quirk": "Regional bank; standard multi-column layout expected.",
    }),
    ("Citizens Bank", ["citizens bank", "citizens", "citizens financial"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — regional Northeast bank",
        "quirk": "Regional bank; standard multi-column layout expected.",
    }),
    ("Capital One", ["capital one", "capitalone", "capital one 360"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — 360 checking/savings + credit cards",
        "quirk": "Both checking and credit card layouts; detect subtype from text.",
    }),
    ("Charles Schwab Bank", ["schwab", "charles schwab", "schwab bank", "schwab brokerage"], ["description", "debit", "credit", "balance"], {
        "source": "Tier 2 research — brokerage-linked checking",
        "quirk": "Brokerage-linked checking; may have investment-like line items.",
    }),
]


def _marker_present(text_lower: str, marker: str) -> bool:
    """Check if a marker is present; use whole-word matching for single-word markers to avoid false positives."""
    if " " in marker:
        return marker in text_lower
    return re.search(rf"\b{re.escape(marker)}\b", text_lower) is not None


def detect_institution(text: str) -> str:
    """Detect financial institution from raw PDF text."""
    text_lower = text.lower()
    for canonical, markers, _, _ in _INSTITUTION_REGISTRY:
        if any(_marker_present(text_lower, marker) for marker in markers):
            return canonical
    return "unknown"


def detect_institution_with_columns(text: str) -> Dict[str, object]:
    """Detect institution and return a confidence + expected column patterns + notes."""
    text_lower = text.lower()
    best = {
        "institution": "unknown",
        "confidence": 0.0,
        "layout": "generic",
        "expected_columns": [],
        "notes": {},
    }
    for canonical, markers, columns, notes in _INSTITUTION_REGISTRY:
        hits = sum(1 for marker in markers if _marker_present(text_lower, marker))
        if hits == 0:
            continue
        confidence = min(0.3 + 0.25 * hits, 0.95)
        layout = "single_column" if canonical in {"Cash App", "Chime"} else "multi_column"
        if confidence > best["confidence"]:
            best = {
                "institution": canonical,
                "confidence": round(confidence, 2),
                "layout": layout,
                "expected_columns": columns,
                "notes": notes,
            }
    return best


INSTITUTION_ALIASES = {
    "EdFed": ["Educational Federal Credit Union", "EdFed CU"],
    "Cash App": ["CashApp", "Square Cash"],
    "TD Bank": ["TDBusiness"],
    "Navy Federal": ["Navy Federal Credit Union", "Navy FCU"],
    "U.S. Bank": ["US Bank", "U.S. Bancorp"],
    "Citibank": ["Citi", "Citigroup"],
    "PNC Bank": ["PNC"],
    "Ally Bank": ["Ally"],
    "SoFi": ["SoFi Bank"],
    "Truist": ["Truist Bank"],
    "Discover Bank": ["Discover"],
    "Marcus by Goldman Sachs": ["Marcus", "Goldman Sachs Bank"],
    "BECU": ["Boeing Employees Credit Union"],
    "American Express": ["Amex", "AMEX", "American Express Company"],
    "USAA": ["USAA Bank", "USAA Federal Savings Bank"],
    "PenFed": ["Pentagon Federal Credit Union"],
    "Alliant Credit Union": ["Alliant"],
    "Synchrony Bank": ["Synchrony", "Synchrony Financial"],
    "Huntington Bank": ["Huntington National Bank", "Huntington"],
    "Citizens Bank": ["Citizens", "Citizens Financial"],
    "Capital One": ["CapitalOne", "Capital One 360", "COF"],
    "Charles Schwab Bank": ["Schwab Bank", "Charles Schwab", "Schwab"],
}


def parse_statement_pdf(pdf_path: str, parse_options: Optional[Dict[str, Any]] = None) -> Any:
    """Route a PDF to the appropriate parser based on caller options.

    If `force_ocr` is True (and OCR is available), use the OCR-first parser.
    Otherwise attempt institution-specific parsing; fall back to the existing
    GenericPDFParser (which has its own silent OCR fallback for low-text PDFs).
    """
    from backend.local.guards import validate_pdf_safety
    from .generic_pdf import GenericPDFParser
    from .ocr_parser import OCRPDFParser
    from .tdbank import TDBankParser
    from .chime import ChimeParser
    from .edfed import EdFedParser
    from .queensborough import QueensboroughParser
    from .bankofamerica import BankOfAmericaParser
    from .chase import ChaseParser
    from .wellsfargo import WellsFargoParser
    from .navyfederal import NavyFederalParser
    from .usbank import USBankParser
    from .citibank import CitibankParser
    from .pnc import PNCBankParser
    from .ally import AllyBankParser
    from .sofi import SoFiParser
    from .truist import TruistParser
    from .becu import BECUParser
    from .discover import DiscoverBankParser
    from .marcus import MarcusParser
    from .cashapp import CashAppParser
    from .amex import AmexParser
    from .usaa import USAAParser
    from .penfed import PenFedParser
    from .alliant import AlliantParser
    from .synchrony import SynchronyBankParser
    from .huntington import HuntingtonBankParser
    from .citizens import CitizensBankParser
    from .capitalone import CapitalOneParser
    from .schwab import SchwabBankParser

    options = parse_options or {}
    # Defense-in-depth: run the guard before any parser library is imported.
    validate_pdf_safety(pdf_path, max_pages=options.get("max_pages", 100))

    # OCR-first path
    if options.get("force_ocr"):
        if not OCRPDFParser.supported():
            raise RuntimeError(
                "force_ocr requested but OCR is not available. "
                "Install Tesseract, Poppler, pytesseract, pdf2image."
            )
        parser = OCRPDFParser(pdf_path, **{
            k: v for k, v in options.items()
            if k in {"language", "dpi", "grayscale", "max_pages"}
        })
        result = parser.parse()
        result["needs_review"] = True  # OCR text needs human validation
        return result

    # Extract raw text once and dispatch by institution
    generic_parser = GenericPDFParser(pdf_path)
    raw_text = "\n".join(generic_parser.extract_text())

    institution = detect_institution(raw_text)
    specific_parsers = {
        "TD Bank": TDBankParser,
        "Chime": ChimeParser,
        "EdFed": EdFedParser,
        "Queensborough National Bank": QueensboroughParser,
        "Bank of America": BankOfAmericaParser,
        "Chase": ChaseParser,
        "Wells Fargo": WellsFargoParser,
        "Navy Federal": NavyFederalParser,
        "U.S. Bank": USBankParser,
        "Citibank": CitibankParser,
        "PNC Bank": PNCBankParser,
        "Ally Bank": AllyBankParser,
        "SoFi": SoFiParser,
        "Truist": TruistParser,
        "BECU": BECUParser,
        "Discover Bank": DiscoverBankParser,
        "Marcus by Goldman Sachs": MarcusParser,
        "Cash App": CashAppParser,
        "American Express": AmexParser,
        "USAA": USAAParser,
        "PenFed": PenFedParser,
        "Alliant Credit Union": AlliantParser,
        "Synchrony Bank": SynchronyBankParser,
        "Huntington Bank": HuntingtonBankParser,
        "Citizens Bank": CitizensBankParser,
        "Capital One": CapitalOneParser,
        "Charles Schwab Bank": SchwabBankParser,
    }

    if institution in specific_parsers:
        parser_cls = specific_parsers[institution]
        if parser_cls.can_handle(raw_text):
            return parser_cls.parse(pdf_path, raw_text)

    if institution == "unknown":
        return {
            "template": None,
            "account_info": {
                "opening_balance": None,
                "closing_balance": None,
                "template_name": None,
                "institution": None,
            },
            "transactions": [],
            "reconciliation": {
                "opening_balance": None,
                "closing_balance": None,
                "transaction_sum": 0.0,
                "variance": None,
                "balanced": None,
            },
            "meta": {
                "total_pages": 0,
                "total_raw_transactions": 0,
                "duplicates_removed": 0,
            },
            "needs_review": True,
        }

    # Known institution but no specific parser; fall back to generic template matching
    result = generic_parser.parse()
    if hasattr(result, "model_dump"):
        result = result.model_dump()
    elif hasattr(result, "dict"):
        result = result.dict()
    result.setdefault("needs_review", False)
    return result
