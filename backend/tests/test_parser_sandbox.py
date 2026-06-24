"""Tests for the PDF parser subprocess sandbox."""
from __future__ import annotations

import os
import tempfile
import time

import pytest

from backend.parsers.sandbox import SandboxError, SandboxTimeout, run_in_sandbox


def _make_pdf(title: str, lines: list[str]) -> str:
    """Create a tiny text-based PDF fixture using fpdf."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in lines:
        pdf.cell(0, 10, line, new_x="LMARGIN", new_y="NEXT")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf.output(tmp.name)
    return tmp.name


def test_sandbox_parses_valid_pdf():
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
        result = run_in_sandbox(
            "backend.parsers.institution:parse_statement_pdf", path
        )
        assert result["template"] == "TD Bank"
        assert len(result["transactions"]) >= 1
        assert "reconciliation" in result
        assert "meta" in result
    finally:
        os.unlink(path)


def test_sandbox_regression_fixture_parses():
    """A regression-style fixture must still produce the canonical shape."""
    path = _make_pdf(
        "Chase Statement",
        [
            "JPMorgan Chase",
            "Statement Period: 01/01/2025 to 01/31/2025",
            "01/15/2025 Coffee Shop $5.00 $95.00",
        ],
    )
    try:
        result = run_in_sandbox(
            "backend.parsers.institution:parse_statement_pdf", path
        )
        assert "template" in result
        assert "account_info" in result
        assert "transactions" in result
        assert "reconciliation" in result
        assert "meta" in result
        assert "needs_review" in result
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Malformed / adversarial behaviour simulations
# ---------------------------------------------------------------------------

def _loop_forever():
    while True:
        time.sleep(0.05)


def test_sandbox_timeout_kills_infinite_loop():
    with pytest.raises(SandboxTimeout):
        run_in_sandbox(
            "backend.tests.test_parser_sandbox:_loop_forever",
            timeout_seconds=1.0,
            max_memory_mb=128,
        )


def _allocate_memory_mb(mb: int):
    """Allocate a block of memory larger than the test sandbox budget."""
    chunk_size = 1 * 1024 * 1024  # 1 MiB
    target = mb * 1024 * 1024
    chunks = bytearray()
    while len(chunks) < target:
        chunks += bytearray(chunk_size)
    return f"allocated {len(chunks)} bytes"


def test_sandbox_memory_limit_kills_hog():
    with pytest.raises(SandboxError) as exc_info:
        # Ask the child to allocate 256 MiB while its budget is 50 MiB.
        run_in_sandbox(
            "backend.tests.test_parser_sandbox:_allocate_memory_mb",
            256,
            timeout_seconds=10.0,
            max_memory_mb=50,
        )
    assert "allocated" not in str(exc_info.value)


def _raise_value_error():
    raise ValueError("simulated parser failure")


def test_sandbox_exception_returns_error_not_traceback():
    with pytest.raises(SandboxError) as exc_info:
        run_in_sandbox(
            "backend.tests.test_parser_sandbox:_raise_value_error",
            timeout_seconds=5.0,
        )
    assert "simulated parser failure" in str(exc_info.value)
    # The response must not contain the raw Python traceback.
    assert "Traceback" not in str(exc_info.value)



# ---------------------------------------------------------------------------
# PDF safety validation (TASK-038.4)
# ---------------------------------------------------------------------------

def _make_pdf_with_javascript() -> str:
    """Create a PDF with embedded document-level JavaScript."""
    import PyPDF2
    writer = PyPDF2.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_js("app.alert('malicious');")
    path = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    with open(path, "wb") as f:
        writer.write(f)
    return path


def _make_multi_page_pdf(pages: int) -> str:
    """Create a PDF with the requested number of blank pages."""
    import PyPDF2
    writer = PyPDF2.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    path = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
    with open(path, "wb") as f:
        writer.write(f)
    return path


def test_pdf_guard_rejects_embedded_javascript():
    from backend.local.guards import PDFSecurityError, validate_pdf_safety

    path = _make_pdf_with_javascript()
    try:
        with pytest.raises(PDFSecurityError) as exc_info:
            validate_pdf_safety(path)
        assert "JavaScript" in str(exc_info.value) or "actions" in str(exc_info.value)
    finally:
        os.unlink(path)


def test_pdf_guard_rejects_oversized_file():
    from backend.local.guards import PDFSecurityError, validate_pdf_safety

    path = _make_pdf(
        "Small Statement",
        ["Statement Period: 01/01/2025 to 01/31/2025", "Opening Balance: $100.00"],
    )
    try:
        with pytest.raises(PDFSecurityError) as exc_info:
            validate_pdf_safety(path, max_file_size_bytes=10)
        assert "size" in str(exc_info.value).lower()
    finally:
        os.unlink(path)


def test_pdf_guard_rejects_too_many_pages():
    from backend.local.guards import PDFSecurityError, validate_pdf_safety

    path = _make_multi_page_pdf(5)
    try:
        with pytest.raises(PDFSecurityError) as exc_info:
            validate_pdf_safety(path, max_pages=3)
        assert "pages" in str(exc_info.value).lower()
    finally:
        os.unlink(path)


def test_sandbox_rejects_pdf_with_embedded_javascript():
    path = _make_pdf_with_javascript()
    try:
        with pytest.raises(SandboxError) as exc_info:
            run_in_sandbox(
                "backend.parsers.institution:parse_statement_pdf",
                path,
                timeout_seconds=5.0,
            )
        msg = str(exc_info.value).lower()
        assert "javascript" in msg or "actions" in msg or "security" in msg
    finally:
        os.unlink(path)


def test_sandbox_rejects_pdf_with_too_many_pages():
    path = _make_multi_page_pdf(110)
    try:
        with pytest.raises(SandboxError) as exc_info:
            run_in_sandbox(
                "backend.parsers.institution:parse_statement_pdf",
                path,
                timeout_seconds=5.0,
            )
        msg = str(exc_info.value).lower()
        assert "pages" in msg or "invalid json" in msg or "sandbox" in msg
    finally:
        os.unlink(path)
