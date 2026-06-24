"""Shared API utility helpers for TaxFlow Pro v3.9.

Replaces ad-hoc upload/output path logic with project-root-scoped helpers
and a small JSON event logger used by the optional api_db logger path.
All helpers are deterministic and local — no cloud dependency.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.security.path_safety import sanitize_filename, safe_user_filename


_BASE_DIR = Path(__file__).resolve().parent.parent


def get_upload_dir() -> Path:
    """Return the canonical upload directory, creating it if needed."""
    upload_dir = _BASE_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def get_output_dir() -> Path:
    """Return the canonical output directory, creating it if needed."""
    output_dir = _BASE_DIR / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_data_dir() -> Path:
    """Return the canonical data directory."""
    data_dir = _BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def safe_filename(user_id: int, original_filename: str) -> str:
    """Build a user-scoped safe filename for uploaded files."""
    return safe_user_filename(user_id, original_filename)


def store_uploaded_file(user_id: int, filename: str, file_bytes: bytes) -> Path:
    """Persist uploaded bytes to the canonical upload directory."""
    upload_dir = get_upload_dir()
    safe_name = safe_filename(user_id, filename)
    path = upload_dir / safe_name
    path.write_bytes(file_bytes)
    return path


def append_event_log(event_type: str, payload: Dict[str, Any]) -> Path:
    """Append a JSON event to the daily api event log."""
    log_dir = _BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = log_dir / f"api_{today}.log"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "payload": payload,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return log_path
