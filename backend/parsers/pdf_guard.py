"""Static guards for suspicious PDF content before parsing begins.

These checks inspect the raw PDF bytes *without* invoking pdfplumber/PyMuPDF,
so a malformed or malicious file cannot exploit the parser just because we
opened it. Intended to run in the parent process before entering the sandbox,
and also inside the sandbox as defense-in-depth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import BinaryIO


MAX_FILE_SIZE_BYTES_DEFAULT = 32 * 1024 * 1024  # 32 MiB
MAX_PAGES_DEFAULT = 100

# PDF action keywords that execute behavior (JavaScript, network, launch, etc.).
# /OpenAction is treated as suspicious only if paired with /JS, /URI, etc.
_FORBIDDEN_ACTIONS = [
    b"/JS",
    b"/JavaScript",
    b"/Launch",
    b"/SubmitForm",
    b"/ImportData",
    b"/URI",
    b"/EmbeddedFile",
    b"/RichMedia",
    b"/AA",  # additional actions dictionary
]

# /OpenAction by itself is usually just "open to page 1" and is emitted by
# many benign generators (including fpdf). Treat it as hostile only when one
# of the forbidden action keys above is also present.
_OPEN_ACTION_KEY = b"/OpenAction"

# Suspicious object stream/filter names that often precede obfuscation/embedded content.
# These are treated as obfuscation only if a forbidden action is also present.
_SUSPICIOUS_FILTERS = [
    b"/ASCIIHexDecode",
    b"/ASCII85Decode",
    b"/LZWDecode",
    b"/Crypt",
]

# Filters that fpdf uses legitimately for normal content streams.
_NORMAL_FPDF_FILTERS = [b"/FlateDecode", b"/DCTDecode"]


class PDFGuardError(Exception):
    """Raised when a PDF fails static safety checks."""


@dataclass(frozen=True)
class PDFGuardResult:
    ok: bool
    page_count: int | None
    file_size_bytes: int
    has_javascript: bool
    has_embedded_files: bool
    has_actions: bool
    has_obfuscated_streams: bool
    reason: str | None = None


def _count_pages(data: bytes) -> int:
    """Fast page count from raw PDF bytes.

    Counts /Type /Page objects that are *not* followed by /Parent within the
    same object declaration. This avoids double-counting template pages and is
    good enough for a guard before parsing.
    """
    count = 0
    for m in re.finditer(rb"/Type\s+/Page(?=\s|/|\]|\r|\n|>>)", data, re.IGNORECASE):
        start = m.end()
        # Skip if a /Parent reference appears in the same dictionary.
        end = data.find(b">>", start)
        if end == -1:
            end = start + 512
        window = data[start:end]
        if b"/Parent" in window:
            continue
        count += 1
    return count


def _count_pages_fast(data: bytes) -> int:
    """Fast upper-bound page count via /Type /Pages /Count N."""
    counts = re.findall(rb"/Type\s*/Pages.*?/Count\s+(\d+)", data, re.DOTALL | re.IGNORECASE)
    return max([int(c) for c in counts], default=0)


def _find_any(data: bytes, needles: list[bytes]) -> bool:
    return any(needle in data for needle in needles)


def _extract_version(data: bytes) -> str | None:
    if data.startswith(b"%PDF-") and len(data) >= 8:
        return data[5:8].decode("latin-1", errors="replace").strip()
    return None


def inspect_pdf(
    data: bytes,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES_DEFAULT,
    max_pages: int = MAX_PAGES_DEFAULT,
    allow_javascript: bool = False,
    allow_embedded_files: bool = False,
    allow_actions: bool = False,
    allow_obfuscated_streams: bool = False,
) -> PDFGuardResult:
    """Inspect raw PDF bytes and return a guard result.

    Does not execute any PDF content; only looks at the byte stream.
    """
    file_size = len(data)
    if file_size > max_size_bytes:
        return PDFGuardResult(
            ok=False,
            page_count=None,
            file_size_bytes=file_size,
            has_javascript=False,
            has_embedded_files=False,
            has_actions=False,
            has_obfuscated_streams=False,
            reason=f"PDF exceeds size limit ({file_size} bytes > {max_size_bytes} bytes)",
        )

    if file_size < 5 or not data.startswith(b"%PDF-"):
        return PDFGuardResult(
            ok=False,
            page_count=None,
            file_size_bytes=file_size,
            has_javascript=False,
            has_embedded_files=False,
            has_actions=False,
            has_obfuscated_streams=False,
            reason="File does not have a valid PDF magic header",
        )

    version = _extract_version(data)
    if version:
        try:
            major, minor = version.split(".", 1)
            if int(major) < 1:
                return PDFGuardResult(
                    ok=False,
                    page_count=None,
                    file_size_bytes=file_size,
                    has_javascript=False,
                    has_embedded_files=False,
                    has_actions=False,
                    has_obfuscated_streams=False,
                    reason=f"PDF version {version} is not supported (minimum 1.0)",
                )
        except ValueError:
            pass

    page_count = _count_pages(data)
    if page_count == 0:
        page_count = _count_pages_fast(data)
    if page_count > max_pages:
        return PDFGuardResult(
            ok=False,
            page_count=page_count,
            file_size_bytes=file_size,
            has_javascript=False,
            has_embedded_files=False,
            has_actions=False,
            has_obfuscated_streams=False,
            reason=f"PDF has too many pages ({page_count} > {max_pages})",
        )

    has_javascript = b"/JavaScript" in data or b"/JS" in data
    has_embedded_files = b"/EmbeddedFile" in data or b"/EmbeddedFiles" in data
    has_forbidden_actions = _find_any(data, _FORBIDDEN_ACTIONS)
    has_open_action = _OPEN_ACTION_KEY in data
    # Treat /OpenAction as hostile only if there are real forbidden actions too.
    has_actions = has_forbidden_actions or (has_open_action and has_forbidden_actions)
    # Treat unusual filters as obfuscation only if an action is also present
    # and none of the normal PDF filters dominate the stream dictionary.
    suspicious_filter_present = _find_any(data, _SUSPICIOUS_FILTERS)
    normal_filter_present = _find_any(data, _NORMAL_FPDF_FILTERS)
    has_obfuscated_streams = has_actions and suspicious_filter_present and not normal_filter_present

    reasons: list[str] = []
    if has_javascript and not allow_javascript:
        reasons.append("PDF contains JavaScript")
    if has_embedded_files and not allow_embedded_files:
        reasons.append("PDF contains embedded files")
    if has_actions and not allow_actions:
        reasons.append("PDF contains executable actions")
    if has_obfuscated_streams and not allow_obfuscated_streams:
        reasons.append("PDF contains obfuscated executable streams")

    if reasons:
        return PDFGuardResult(
            ok=False,
            page_count=page_count,
            file_size_bytes=file_size,
            has_javascript=has_javascript,
            has_embedded_files=has_embedded_files,
            has_actions=has_actions,
            has_obfuscated_streams=has_obfuscated_streams,
            reason="; ".join(reasons),
        )

    return PDFGuardResult(
        ok=True,
        page_count=page_count,
        file_size_bytes=file_size,
        has_javascript=has_javascript,
        has_embedded_files=has_embedded_files,
        has_actions=has_actions,
        has_obfuscated_streams=has_obfuscated_streams,
    )


def raise_for_pdf(data: bytes, **kwargs) -> None:
    """Run inspect_pdf and raise PDFGuardError if it fails."""
    result = inspect_pdf(data, **kwargs)
    if not result.ok:
        raise PDFGuardError(result.reason or "PDF failed safety checks")


def inspect_pdf_file(
    path: str,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES_DEFAULT,
    max_pages: int = MAX_PAGES_DEFAULT,
    **kwargs,
) -> PDFGuardResult:
    """Convenience wrapper to inspect a PDF on disk."""
    with open(path, "rb") as f:
        return inspect_pdf(
            f.read(),
            max_size_bytes=max_size_bytes,
            max_pages=max_pages,
            **kwargs,
        )
