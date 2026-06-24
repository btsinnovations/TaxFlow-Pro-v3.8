"""PII/PCI redaction helpers for TaxFlow Pro v3.9.

Rules:
- Account/card numbers are masked to last 4 digits (or a fixed mask if shorter).
- Raw sensitive descriptions are replaced with a redacted token.
- Raw data stays in the DB; these helpers only apply to output surfaces:
  audit logs, exports, summaries, and signed artifacts.
"""
from __future__ import annotations

import re


def mask_account_number(value: str | None, reveal: int = 4) -> str | None:
    """Mask a full account/card number to its last `reveal` digits.

    Keeps non-digit-looking strings as-is (e.g., already masked values).
    Returns the original value unchanged if it is None or empty.
    """
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return value
    if len(digits) <= reveal:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - reveal)}{digits[-reveal:]}"


def redact_description(description: str | None) -> str | None:
    """Replace a raw sensitive description with a generic redacted marker.

    Use this for export/audit surfaces when the full description may contain
    account numbers, PII, or other sensitive tokens.
    """
    if description is None:
        return None
    return "[REDACTED]"


def redact_text(text: str | None) -> str | None:
    """Generic top-level redaction helper.

    Currently returns a fixed marker. Future versions can apply
    selective masking (e.g., regex-based account number detection).
    """
    if text is None:
        return None
    return "[REDACTED]"


def mask_transaction_description(description: str | None) -> str | None:
    """Mask any obvious account/card numbers embedded in a description.

    Keeps the rest of the description readable so exports remain useful.
    Only removes digit sequences that look like account/card numbers (9+ digits).
    """
    if description is None:
        return None
    return re.sub(r"\b\d{9,}\b", lambda m: mask_account_number(m.group(0)) or "", description)


def redact_pii(value: str | None) -> str | None:
    """Redact a raw string field by replacing it with a fixed marker.

    Used by the audit trail before persisting free-text descriptions so that
    full sensitive strings do not enter the signed chain.
    """
    return redact_description(value)


def redact_pii_in_json(payload: dict | list | str | int | float | bool | None) -> dict | list | str | int | float | bool | None:
    """Recursively redact PII in JSON-serializable structures.

    Keys containing account/card/routing/tax identifiers are masked to last 4.
    Values that are free-text descriptions are fully redacted.
    """
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            lower = key.lower()
            if any(part in lower for part in ("account_number", "card_number", "routing_number", "tax_id")):
                out[key] = mask_account_number(str(value)) if value is not None else None
            elif "description" in lower or "memo" in lower:
                out[key] = redact_description(str(value)) if value is not None else None
            else:
                out[key] = redact_pii_in_json(value)
        return out
    if isinstance(payload, list):
        return [redact_pii_in_json(item) for item in payload]
    if isinstance(payload, str):
        # Heuristic: long digit runs get masked; otherwise leave text alone.
        return mask_transaction_description(payload)
    return payload