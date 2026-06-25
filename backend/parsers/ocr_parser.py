"""OCR-first PDF parser for TaxFlow Pro v3.9.1 (P1.2).

This parser is surfaced as an explicit, optional choice at upload time. It does
not replace the OCR fallback in `GenericPDFParser`; it just gives users a way to
force OCR when they know a PDF contains scanned pages.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

from backend.utils.temp_file_cleanup import TemporaryOCRDirectory


def _raise_if_unsafe(pdf_path: str, max_pages: int = 100) -> None:
    """Run the shared static PDF guard before OCR-dependent imports."""
    from backend.local.guards import validate_pdf_safety

    validate_pdf_safety(pdf_path, max_pages=max_pages)

try:
    from pdf2image import convert_from_path
except Exception:  # pragma: no cover
    convert_from_path = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None
else:
    # Honor vendored Tesseract binary set by launcher.
    _TESSERACT_CMD = os.environ.get("TESSERACT_CMD")
    if _TESSERACT_CMD:
        import pytesseract.pytesseract as _pytess
        _pytess.tesseract_cmd = _TESSERACT_CMD
    _POPPLER_PATH = os.environ.get("POPPLER_PATH")


@dataclass
class OCRPage:
    page_number: int
    text: str
    tables: List[Dict[str, Any]] = field(default_factory=list)


class OCRPDFParser:
    """Parse a PDF by converting pages to images and running Tesseract OCR."""

    def __init__(
        self,
        pdf_path: str,
        language: str = "eng",
        dpi: int = 300,
        grayscale: bool = False,
        max_pages: int = 100,
        **kwargs: Any,
    ):
        self.pdf_path = pdf_path
        self.language = language
        self.dpi = dpi
        self.grayscale = grayscale
        self.max_pages = max_pages
        self._extra: Dict[str, Any] = kwargs
        self._check_supported()

    @classmethod
    def supported(cls) -> bool:
        """Return True if pdf2image, pytesseract, and the Tesseract CLI are available."""
        if convert_from_path is None or pytesseract is None:
            return False

        tesseract_cmd = getattr(pytesseract, "tesseract_cmd", "tesseract")
        if not shutil.which(tesseract_cmd) and not shutil.which("tesseract"):
            return False
        return True

    def _check_supported(self) -> None:
        if self.supported():
            return
        raise RuntimeError(
            "OCR parsing is not available on this system. "
            "Install Tesseract OCR (https://github.com/tesseract-ocr/tesseract) "
            "and Poppler (https://poppler.freedesktop.org/), then install Python deps: "
            "pip install pytesseract pdf2image Pillow"
        )

    def _preprocess(self, image: Any) -> Any:
        if not self.grayscale:
            return image
        try:
            return image.convert("L")
        except Exception:
            return image

    def extract_pages(self) -> List[OCRPage]:
        """Return one OCRPage per PDF page."""
        _raise_if_unsafe(self.pdf_path, max_pages=self.max_pages)
        if convert_from_path is None or pytesseract is None:
            raise RuntimeError("OCR dependencies are not available")

        pages: List[OCRPage] = []
        with TemporaryOCRDirectory() as output_folder:
            images = convert_from_path(
                self.pdf_path,
                dpi=self.dpi,
                fmt="png",
                output_folder=str(output_folder),
                **({"poppler_path": _POPPLER_PATH} if _POPPLER_PATH else {}),
            )
            for idx, image in enumerate(images[: self.max_pages], start=1):
                processed = self._preprocess(image)
                text = pytesseract.image_to_string(
                    processed, lang=self.language
                )
                pages.append(OCRPage(page_number=idx, text=text or ""))
        return pages

    def parse(self) -> Dict[str, Any]:
        """Return a GenericPDFParser-compatible dict shape.

        The return value mirrors what `GenericPDFParser.parse()` produces:
        {
            "meta": {...},
            "reconciliation": {...},
            "transactions": [...],
            "template": {...},
        }
        """
        pages = self.extract_pages()
        full_text = "\n\n".join(p.text for p in pages if p.text)

        # We intentionally do not perform statement-level transaction parsing here.
        # The existing GenericPDFParser / transaction_builder pipeline is still the
        # right place for layout-specific extraction. OCR parser's job is to make the
        # scanned text available so that pipeline can run.
        return {
            "meta": {
                "pages": len(pages),
                "parser": "ocr",
                "ocr_language": self.language,
                "ocr_dpi": self.dpi,
                "ocr_grayscale": self.grayscale,
                "period_start": None,
                "period_end": None,
            },
            "reconciliation": {
                "opening_balance": None,
                "closing_balance": None,
                "variance": None,
                "balanced": None,
            },
            "transactions": [],
            "pages": [p.__dict__ for p in pages],
            "template": None,
            "raw_text": full_text,
        }


def parse_pdf_to_cr_dict(pdf_path: str, **options: Any) -> Dict[str, Any]:
    """Convenience wrapper used by institution.py / upload router."""
    parser = OCRPDFParser(pdf_path, **options)
    return parser.parse()
