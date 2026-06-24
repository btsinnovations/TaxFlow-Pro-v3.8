"""Tests for the first-class OCR PDF parser (P1.2)."""
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch, ANY

import pytest

from backend.parsers.ocr_parser import OCRPDFParser


# -----------------------------------------------------------------------------
# 1. supported() returns a bool and is consistent across calls
# -----------------------------------------------------------------------------
def test_supported_returns_bool():
    result = OCRPDFParser.supported()
    assert isinstance(result, bool)
    assert OCRPDFParser.supported() == result


# -----------------------------------------------------------------------------
# 2. Constructor raises a clear RuntimeError when deps are unavailable.
# -----------------------------------------------------------------------------
def test_constructor_raises_when_unsupported():
    with patch.object(OCRPDFParser, "supported", return_value=False):
        with pytest.raises(RuntimeError) as exc_info:
            OCRPDFParser("dummy.pdf")
    msg = str(exc_info.value).lower()
    assert "tesseract" in msg
    assert "poppler" in msg
    assert "pytesseract" in msg
    assert "pdf2image" in msg


# -----------------------------------------------------------------------------
# 3. Graceful degradation when imports are missing.
# -----------------------------------------------------------------------------
def test_supported_false_when_imports_missing():
    """Simulate a system where pytesseract/pdf2image cannot be imported."""
    modules_before = set(sys.modules.keys())

    # Create fake modules that raise on attribute access to mimic missing deps.
    class BrokenModule(ModuleType):
        def __getattr__(self, name: str):
            raise ImportError(f"No module named '{name}'")

    broken_pdf2image = BrokenModule("pdf2image")
    broken_pytesseract = BrokenModule("pytesseract")
    broken_pytesseract.tesseract_cmd = "tesseract"

    with patch.dict(
        sys.modules,
        {"pdf2image": broken_pdf2image, "pytesseract": broken_pytesseract},
        clear=False,
    ):
        with patch.object(Path, "exists", return_value=False):
            assert OCRPDFParser.supported() is False


# -----------------------------------------------------------------------------
# 4. Functional OCR round-trip using mocked dependencies.
# -----------------------------------------------------------------------------
def _make_pdf_fixture(tmp_path: Path) -> Path:
    """Create a tiny text-based PDF fixture for OCR testing."""
    try:
        from fpdf import FPDF
    except ImportError:  # pragma: no cover
        pytest.skip("fpdf not installed")

    pdf_path = tmp_path / "ocr_fixture.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "TaxFlow Pro OCR Test", ln=True)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, "Scanned page with text.", ln=True)
    pdf.output(str(pdf_path))
    return pdf_path


def test_parse_returns_page_text_with_mocked_ocr(tmp_path: Path):
    """If OCR is supported, ensure the parser returns non-empty text."""
    pdf_path = _make_pdf_fixture(tmp_path)

    # Mock image object so we don't need real pdf2image/PIL conversion.
    mock_image = MagicMock()
    mock_image.convert = MagicMock(return_value=mock_image)

    fake_pages = [mock_image, mock_image]

    with patch("backend.parsers.ocr_parser.OCRPDFParser.supported", return_value=True):
        with patch(
            "backend.parsers.ocr_parser.convert_from_path",
            return_value=fake_pages,
        ) as mock_convert:
            with patch(
                "backend.parsers.ocr_parser.pytesseract.image_to_string",
                side_effect=["TaxFlow Pro OCR Test\nScanned page with text.", ""],
            ) as mock_ocr:
                parser = OCRPDFParser(str(pdf_path), language="eng", dpi=300)
                result = parser.parse()

    assert result["meta"]["parser"] == "ocr"
    assert result["meta"]["pages"] == 2
    assert result["meta"]["ocr_language"] == "eng"
    assert result["meta"]["ocr_dpi"] == 300

    pages = result.get("pages", [])
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "TaxFlow Pro OCR Test" in pages[0]["text"]
    assert pages[1]["page_number"] == 2

    assert "TaxFlow Pro OCR Test" in result.get("raw_text", "")

    mock_convert.assert_called_once_with(str(pdf_path), dpi=300, fmt="png", output_folder=ANY)
    _, call_kwargs = mock_convert.call_args
    assert Path(call_kwargs["output_folder"]).exists() is False
    assert mock_ocr.call_count == 2


# -----------------------------------------------------------------------------
# 5. Grayscale preprocessing path.
# -----------------------------------------------------------------------------
def test_grayscale_preprocessing(tmp_path: Path):
    pdf_path = _make_pdf_fixture(tmp_path)

    mock_image = MagicMock()
    mock_image.convert = MagicMock(return_value=mock_image)

    with patch("backend.parsers.ocr_parser.OCRPDFParser.supported", return_value=True):
        with patch(
            "backend.parsers.ocr_parser.convert_from_path",
            return_value=[mock_image],
        ):
            with patch(
                "backend.parsers.ocr_parser.pytesseract.image_to_string",
                return_value="grayscale test",
            ):
                parser = OCRPDFParser(str(pdf_path), grayscale=True)
                pages = parser.extract_pages()

    assert len(pages) == 1
    assert pages[0].text == "grayscale test"
    mock_image.convert.assert_called_once_with("L")
