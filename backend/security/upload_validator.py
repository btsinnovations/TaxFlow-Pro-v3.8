"""Upload validation for TaxFlow Pro /api/upload.

Rejects malicious or mislabeled uploads before they are written to disk.
Default limits:
  - Max size: 32 MiB (override with TAXFLOW_MAX_UPLOAD_BYTES)
  - File extension: .pdf only
  - Declared MIME type: application/pdf
  - Magic header: first 5 bytes must be %PDF-
  - Optional strict mode (TAXFLOW_UPLOAD_MAGIC_STRICT=true): version must be 1.x or 2.x
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile


# 32 MiB default. Override with TAXFLOW_MAX_UPLOAD_BYTES environment variable.
MAX_UPLOAD_SIZE_BYTES = int(
    os.environ.get("TAXFLOW_MAX_UPLOAD_BYTES", 32 * 1024 * 1024)
)

# Optional strict PDF-version check.
MAGIC_STRICT = os.environ.get("TAXFLOW_UPLOAD_MAGIC_STRICT", "").lower() in (
    "1",
    "true",
    "yes",
)

_ALLOWED_EXTENSION = ".pdf"
_ALLOWED_MIME_TYPE = "application/pdf"
_PDF_MAGIC = b"%PDF-"


def _human_size(num_bytes: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TiB"


async def validate_upload_file(file: UploadFile, filename: str) -> bytes:
    """Validate an upload and return its contents.

    Raises HTTPException with 413 for oversized files and 415 for files that
    fail extension, MIME-type, or magic-header checks. The file is read into
    memory only up to ``MAX_UPLOAD_SIZE_BYTES + 1`` bytes, and the returned
    bytes are the full (validated) file contents for downstream use.
    """
    # 1. Extension whitelist
    if not filename.lower().endswith(_ALLOWED_EXTENSION):
        raise HTTPException(
            status_code=415,
            detail=f"Only PDF files are accepted (got extension: {Path(filename).suffix!r})",
        )

    # 2. Declared MIME type
    if file.content_type and file.content_type.lower() != _ALLOWED_MIME_TYPE:
        raise HTTPException(
            status_code=415,
            detail=f"Invalid MIME type: {file.content_type!r}. Only application/pdf is accepted.",
        )

    # 3. Size + magic-header check in a single bounded read.
    contents = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Upload exceeds maximum size of {MAX_UPLOAD_SIZE_BYTES} bytes "
                f"({_human_size(MAX_UPLOAD_SIZE_BYTES)})"
            ),
        )

    if len(contents) < len(_PDF_MAGIC):
        raise HTTPException(
            status_code=415, detail="File too small to be a valid PDF"
        )

    if not contents.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=415,
            detail="File does not have a valid PDF magic header (%PDF-)",
        )

    # 4. Optional strict version check
    if MAGIC_STRICT:
        version_part = contents[len(_PDF_MAGIC) : len(_PDF_MAGIC) + 3]
        if not re.match(rb"[12]\.\d", version_part):
            raise HTTPException(
                status_code=415,
                detail="PDF version must be 1.x or 2.x in strict mode",
            )

    return contents
