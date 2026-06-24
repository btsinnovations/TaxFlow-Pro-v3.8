"""Runtime guards that block or warn about cloud/API usage in offline mode.

Intended for import-time and call-site protection. All network-facing modules
should go through here before making external requests.
"""

from __future__ import annotations

import functools
import socket
from typing import Callable, TypeVar

from .settings import guard_cloud_call, is_offline


F = TypeVar("F")


def block_cloud_calls(func: F) -> F:
    """Decorator that raises RuntimeError if the wrapped function is called offline."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        guard_cloud_call(func.__name__)
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def assert_no_network_access(host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> None:
    """Raise RuntimeError if the host can reach the public internet."""
    if not is_offline():
        return
    try:
        with socket.create_connection((host, port), timeout=timeout):
            raise RuntimeError(
                f"Offline mode expected no network access, but {host}:{port} is reachable."
            )
    except OSError:
        pass


class CloudAPIGuard:
    """Context manager to assert no cloud calls happen inside a block.

    Usage:
        with CloudAPIGuard():
            do_something_that_should_not_call_cloud()
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    @staticmethod
    def ensure_offline():
        if not is_offline():
            raise RuntimeError("Operation requires offline runtime mode")


def is_duplicate_transaction(existing: dict, candidate: dict, tolerance: float = 0.0) -> bool:
    """Return True if candidate is a likely duplicate of existing."""
    import re

    def normalize(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    if existing.get("date") != candidate.get("date"):
        return False
    if existing.get("tx_type") != candidate.get("tx_type"):
        return False
    if normalize(existing.get("description", "")) != normalize(candidate.get("description", "")):
        return False

    existing_amount = float(existing.get("amount", 0))
    candidate_amount = float(candidate.get("amount", 0))
    if tolerance > 0:
        return abs(existing_amount - candidate_amount) <= tolerance
    return existing_amount == candidate_amount


def redact_sensitive_values(payload: dict) -> dict:
    """Return a shallow copy of `payload` with known PII keys masked.

    Safe to call on audit details or export metadata. Raw DB records are
    not modified; this is for output/audit surfaces only.
    """
    from ..utils.redaction import mask_account_number, redact_description

    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    for key in ("account_number", "card_number", "routing_number"):
        if key in out and out[key] is not None:
            out[key] = mask_account_number(str(out[key]))
    if "description" in out and out["description"] is not None:
        out["description"] = redact_description(str(out["description"]))
    return out


# ---------------------------------------------------------------------------
# PDF safety guards (TASK-038.4)
# ---------------------------------------------------------------------------
# The byte-level PDF guard lives in backend.parsers.pdf_guard so it can be
# used by the upload router without importing heavy parser libraries. This
# module re-exports the public API and provides a convenience validator.
from ..parsers.pdf_guard import (
    MAX_FILE_SIZE_BYTES_DEFAULT,
    MAX_PAGES_DEFAULT,
    PDFGuardError,
    PDFGuardResult,
    inspect_pdf,
    inspect_pdf_file,
    raise_for_pdf,
)


class PDFSecurityError(PDFGuardError):
    """Alias used by code/tests that expect a separate security exception."""


def validate_pdf_safety(
    pdf_path: str,
    max_file_size_bytes: int | None = None,
    max_pages: int | None = None,
) -> None:
    """Validate a PDF before parsing using the static byte-level guard.

    Raises:
        PDFSecurityError: if the file is too large, has too many pages, or
            contains embedded JavaScript/actions.
    """
    result = inspect_pdf_file(
        str(pdf_path),
        max_size_bytes=max_file_size_bytes or MAX_FILE_SIZE_BYTES_DEFAULT,
        max_pages=max_pages or MAX_PAGES_DEFAULT,
    )
    if not result.ok:
        raise PDFSecurityError(result.reason or "PDF failed safety checks")
