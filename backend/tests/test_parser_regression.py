"""Parser regression harness for P1.1 coverage expansion.

Uses synthetic PDF fixtures to exercise each supported institution parser and
verify the canonical output shape.
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import List

import pytest
from fpdf import FPDF

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.parsers import (
    parse_statement_pdf,
    detect_institution,
    GenericPDFParser,
    TDBankParser,
    ChimeParser,
    EdFedParser,
    QueensboroughParser,
)


def _make_pdf(title: str, lines: List[str]) -> str:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font("Helvetica", "", 10)
    for line in lines:
        pdf.cell(0, 10, line, ln=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.output(tmp.name)
    return tmp.name


def _cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _assert_shape(result: dict) -> None:
    assert "template" in result
    assert "account_info" in result
    assert "transactions" in result
    assert "reconciliation" in result
    assert "meta" in result
    assert "needs_review" in result


def _assert_tx_fields(tx: dict) -> None:
    assert "date" in tx
    assert "description" in tx
    assert "amount" in tx
    assert "type" in tx


# -----------------------------------------------------------------------------
# TD Bank
# -----------------------------------------------------------------------------
def test_td_bank_credit_detection():
    path = _make_pdf(
        "TD Bank Credit Card Statement",
        ["TD Bank Credit Card", "01/15/2025 Coffee Shop $5.00 $95.00"],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "TD Bank"
        assert TDBankParser.can_handle(raw)
        result = TDBankParser.parse(path, raw)
        _assert_shape(result)
        assert result["template"] == "TD Bank"
        assert len(result["transactions"]) >= 1
        _assert_tx_fields(result["transactions"][0])
    finally:
        _cleanup(path)


def test_td_bank_checking_detection():
    path = _make_pdf(
        "TD Bank Statement",
        [
            "TD Bank Checking",
            "Statement Period: 01/01/2025 to 01/31/2025",
            "Opening Balance: $100.00",
            "Closing Balance: $100.00",
            "01/15 Coffee Shop $5.00",
            "01/20 Salary Deposit $50.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "TD Bank"
        result = parse_statement_pdf(path)
        _assert_shape(result)
        assert result["template"] == "TD Bank"
        assert len(result["transactions"]) >= 1
    finally:
        _cleanup(path)


# -----------------------------------------------------------------------------
# Chime
# -----------------------------------------------------------------------------
def test_chime_checking_detection():
    path = _make_pdf(
        "Chime Spending Account",
        [
            "Chime Checking Statement",
            "Spending Account",
            "01/15/2025 Coffee Shop $5.00",
            "01/20/2025 Direct Deposit $50.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "Chime"
        assert ChimeParser.can_handle(raw)
        result = ChimeParser.parse(path, raw)
        _assert_shape(result)
        assert result["template"] == "Chime"
        assert len(result["transactions"]) >= 1
    finally:
        _cleanup(path)


def test_chime_credit_builder_detection():
    path = _make_pdf(
        "Chime Credit Builder",
        [
            "Chime Credit Builder Statement",
            "Credit Builder",
            "01/15/2025 Gas Station $25.00",
            "01/25/2025 Payment $25.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "Chime"
        result = parse_statement_pdf(path)
        _assert_shape(result)
        assert result["template"] == "Chime"
    finally:
        _cleanup(path)


# -----------------------------------------------------------------------------
# EdFed
# -----------------------------------------------------------------------------
def test_edfed_share_draft_detection():
    path = _make_pdf(
        "EdFed Share Draft",
        [
            "Educational Federal Credit Union",
            "ACCOUNT ACTIVITY FOR SHARE DRAFT",
            "01/15/2025 Coffee Shop 5.00 95.00",
            "01/20/2025 Salary 50.00 145.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "EdFed"
        assert EdFedParser.can_handle(raw)
        result = EdFedParser.parse(path, raw)
        _assert_shape(result)
        assert result["template"] == "EdFed"
        assert len(result["transactions"]) >= 1
    finally:
        _cleanup(path)


def test_edfed_credit_detection():
    path = _make_pdf(
        "EdFed Rewards Visa",
        [
            "Educational Federal Credit Union",
            "EdFed Rewards Visa Credit Card",
            "01/15/2025 Coffee Shop $5.00",
            "01/25/2025 Payment -$5.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "EdFed"
        result = parse_statement_pdf(path)
        _assert_shape(result)
        assert result["template"] == "EdFed"
    finally:
        _cleanup(path)


# -----------------------------------------------------------------------------
# BofA / Chase / BECU / Queensborough (detection + routing)
# -----------------------------------------------------------------------------
def test_bofa_detection_and_shape():
    path = _make_pdf(
        "Bank of America Statement",
        [
            "Bank of America",
            "Statement Period: 01/01/2025 to 01/31/2025",
            "01/15/2025 Coffee Shop $5.00 $95.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "Bank of America"
        result = parse_statement_pdf(path)
        _assert_shape(result)
    finally:
        _cleanup(path)


def test_chase_detection_and_shape():
    path = _make_pdf(
        "Chase Statement",
        [
            "JPMorgan Chase",
            "Statement Period: 01/01/2025 to 01/31/2025",
            "01/15/2025 Coffee Shop $5.00 $95.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "Chase"
        result = parse_statement_pdf(path)
        _assert_shape(result)
    finally:
        _cleanup(path)


def test_becu_detection_and_shape():
    path = _make_pdf(
        "BECU Statement",
        [
            "BECU",
            "Boeing Employees Credit Union",
            "Member Share Savings",
            "01/15/2025 Coffee Shop $5.00 $95.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "BECU"
        result = parse_statement_pdf(path)
        _assert_shape(result)
    finally:
        _cleanup(path)


def test_queensborough_detection_and_shape():
    path = _make_pdf(
        "QNB Statement",
        [
            "Queensborough National Bank & Trust",
            "Statement Period: 01/01/2025 to 01/31/2025",
            "01/15/2025 Coffee Shop $5.00",
            "01/20/2025 Deposit $50.00",
        ],
    )
    try:
        text = GenericPDFParser(path).extract_text()
        raw = "\n".join(text)
        assert detect_institution(raw) == "Queensborough National Bank"
        assert QueensboroughParser.can_handle(raw)
        result = QueensboroughParser.parse(path, raw)
        _assert_shape(result)
        assert result["template"] == "Queensborough National Bank"
        assert len(result["transactions"]) >= 1
    finally:
        _cleanup(path)


# -----------------------------------------------------------------------------
# Graceful fallback for unknown institution
# -----------------------------------------------------------------------------
def test_unknown_institution_needs_review():
    path = _make_pdf(
        "Random PDF",
        [
            "Completely Unrelated Document",
            "No financial transactions here.",
        ],
    )
    try:
        result = parse_statement_pdf(path)
        _assert_shape(result)
        assert result["template"] is None
        assert result["needs_review"] is True
        assert result["transactions"] == []
    finally:
        _cleanup(path)
