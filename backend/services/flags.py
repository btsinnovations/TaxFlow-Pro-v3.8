"""Review flag validation helpers for TaxFlow Pro v3.9."""
from __future__ import annotations

from fastapi import HTTPException

from ..schemas import FlagCreate


def validate_flag_target(payload: FlagCreate) -> None:
    """Ensure exactly one of transaction_id or journal_entry_id is provided."""
    has_tx = payload.transaction_id is not None
    has_je = payload.journal_entry_id is not None
    if has_tx == has_je:
        raise HTTPException(
            status_code=422,
            detail="Exactly one of transaction_id or journal_entry_id must be set.",
        )
