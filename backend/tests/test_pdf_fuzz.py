"""Fuzz / corruption tests for PDF static guard and parser sandbox (TASK-038.13)."""
from __future__ import annotations

import io

import pytest

from backend.parsers.pdf_guard import (
    PDFGuardError,
    inspect_pdf,
    raise_for_pdf,
)


# Minimal well-formed PDF header used as a template.
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
trailer
<< /Size 4 /Root 1 0 R >>
startxref
0
%%EOF
"""

# PDF containing a JavaScript action.
PDF_WITH_JS = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R /OpenAction 3 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [4 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Action /S /JavaScript /JS (app.alert(1)) >>
endobj
4 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
trailer
<< /Size 5 /Root 1 0 R >>
startxref
0
%%EOF
"""


def make_oversized_pdf(max_size: int) -> bytes:
    """Return a byte string with a valid PDF header followed by padding."""
    header = MINIMAL_PDF[:128]
    padding_size = max_size - len(header) + 1
    return header + b"\n" + b"0" * padding_size


def make_multi_page_pdf(page_count: int) -> bytes:
    """Return a synthetic PDF byte string declaring many pages."""
    kids = " ".join(f"{i + 2} 0 R" for i in range(page_count))
    objects = f"""1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [{kids}] /Count {page_count} >>
endobj
"""
    for i in range(page_count):
        objects += f"""{i + 2} 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
"""
    return (
        f"""%PDF-1.4
{objects}
trailer
<< /Size {page_count + 2} /Root 1 0 R >>
startxref
0
%%EOF
"""
    ).encode("latin-1")


class TestPDFGuardLimits:
    def test_guard_rejects_oversized_pdf(self):
        from backend.parsers.pdf_guard import MAX_FILE_SIZE_BYTES_DEFAULT

        oversized = make_oversized_pdf(MAX_FILE_SIZE_BYTES_DEFAULT)
        result = inspect_pdf(oversized)
        assert not result.ok
        assert "size limit" in (result.reason or "").lower()
        with pytest.raises(PDFGuardError, match="size limit"):
            raise_for_pdf(oversized)

    def test_guard_rejects_too_many_pages(self):
        from backend.parsers.pdf_guard import MAX_PAGES_DEFAULT

        many_pages = make_multi_page_pdf(MAX_PAGES_DEFAULT + 10)
        result = inspect_pdf(many_pages)
        assert not result.ok
        assert "too many pages" in (result.reason or "").lower()

    def test_guard_accepts_small_pdf(self):
        result = inspect_pdf(MINIMAL_PDF)
        assert result.ok, result.reason
        assert result.page_count == 1

    def test_guard_rejects_pdf_with_javascript(self):
        result = inspect_pdf(PDF_WITH_JS)
        assert not result.ok
        assert result.has_javascript
        assert "javascript" in (result.reason or "").lower()

    def test_guard_rejects_embedded_file_keyword(self):
        data = MINIMAL_PDF.replace(b"endobj\ntrailer", b"/EmbeddedFile endobj\ntrailer")
        result = inspect_pdf(data)
        assert not result.ok
        assert "embedded" in (result.reason or "").lower()

    def test_guard_rejects_launch_action(self):
        data = MINIMAL_PDF.replace(
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>",
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /Launch /F (calc.exe) >> >>",
        )
        result = inspect_pdf(data)
        assert not result.ok
        assert "executable" in (result.reason or "").lower()


class TestParserSandbox:
    def test_sandbox_entry_exists(self):
        from backend.parsers import sandbox_entry

        assert callable(sandbox_entry.main)

    def test_sandbox_entry_rejects_invalid_json(self, capsys):
        from backend.parsers.sandbox_entry import main
        import sys

        payload = "not-json"
        # Patch stdin for this single call.
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            main()
        finally:
            sys.stdin = old_stdin
        captured = capsys.readouterr()
        assert "__sandbox_error__" in captured.out

    def test_sandbox_entry_rejects_missing_target(self, capsys):
        from backend.parsers.sandbox_entry import main
        import sys

        payload = '{"args": []}'
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            main()
        finally:
            sys.stdin = old_stdin
        captured = capsys.readouterr()
        assert "__sandbox_error__" in captured.out
