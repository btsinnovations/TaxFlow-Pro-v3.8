"""
Utilities for the TaxFlow Pro API.
"""

import os
import json
import shutil
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Configurable via environment variables; fall back to project subdirs
def _get_upload_dir() -> Path:
    return Path(os.environ.get("TAXFLOW_UPLOAD_DIR", PROJECT_ROOT / "uploads"))

def _get_output_dir() -> Path:
    data_output = PROJECT_ROOT / "data" / "output"
    if data_output.exists():
        return data_output
    return Path(os.environ.get("TAXFLOW_OUTPUT_DIR", PROJECT_ROOT / "output"))

UPLOAD_DIR = _get_upload_dir()
OUTPUT_DIR = _get_output_dir()
LOGS_DIR = PROJECT_ROOT / "logs"
DB_FILE = PROJECT_ROOT / "api_db.json"


# Ensure directories exist
def ensure_dirs(upload_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
    (upload_dir or UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    (output_dir or OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_FILE.exists():
        save_db({"clients": {}, "audit_log": [], "processed_files": {}})


def get_db() -> Dict[str, Any]:
    if not DB_FILE.exists():
        return {"clients": {}, "audit_log": [], "processed_files": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data: Dict[str, Any]):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def log_event(
    severity: str,
    event_type: str,
    description: str,
    client_id: Optional[str] = None,
    user: str = "system",
    details: Optional[Dict[str, Any]] = None,
):
    db = get_db()
    event = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now().isoformat(),
        "severity": severity,
        "event_type": event_type,
        "client_id": client_id,
        "description": description,
        "user": user,
        "session_id": str(uuid.uuid4())[:12],
        "details": details or {},
    }
    db["audit_log"].insert(0, event)
    db["audit_log"] = db["audit_log"][:10000]
    save_db(db)
    return event


def generate_file_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def save_uploaded_file(file_id: str, upload_file: Any, save_folder: Optional[Path] = None) -> Path:
    ensure_dirs(upload_dir=save_folder)
    ext = Path(upload_file.filename).suffix.lower()
    dest = (save_folder or UPLOAD_DIR) / f"{file_id}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(upload_file.file, f)
    return dest


def get_upload_path(file_id: str, search_folder: Optional[Path] = None) -> Optional[Path]:
    folders = [search_folder] if search_folder else []
    folders += [UPLOAD_DIR]
    for folder in folders:
        if folder is None:
            continue
        for ext in [".pdf", ".csv"]:
            candidate = folder / f"{file_id}{ext}"
            if candidate.exists():
                return candidate
    return None


def get_output_path(file_id: str, fmt: str, output_folder: Optional[Path] = None) -> Path:
    return (output_folder or OUTPUT_DIR) / f"{file_id}.{fmt}"
