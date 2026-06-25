"""Local-first scheduler stub for TaxFlow Pro v3.11.

The recurring transaction engine is intentionally offline-first.  This module
provides a placeholder entry point so the offline scheduler can be wired by
CLI or a future APScheduler-based runner without calling external services.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def schedule_recurring_check(db: "Session" | None = None) -> dict:
    """Placeholder for the recurring-transaction cron-like runner.

    In a full implementation this would evaluate all active rules and
    materialize transactions up to today.  For v3.11 scaffold it returns the
    expected metadata so callers can confirm the hook exists.
    """
    return {
        "ok": True,
        "mode": "offline",
        "checked_at": date.today().isoformat(),
        "materialized": 0,
        "note": "Scheduler stub: no live APIs used; implement runner loop when ready.",
    }
