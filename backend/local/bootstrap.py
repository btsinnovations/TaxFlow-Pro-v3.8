"""Local dependency bootstrap (TASK-038.7).

Detects required local binaries and Python modules without making any
network calls.  Used by the offline self-test endpoint.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BootstrapCheck:
    name: str
    available: bool
    required: bool
    message: str


@dataclass
class BootstrapReport:
    ready: bool
    checks: list[BootstrapCheck] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "checks": [
                {
                    "name": c.name,
                    "available": c.available,
                    "required": c.required,
                    "message": c.message,
                }
                for c in self.checks
            ],
        }


def _module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _binary_available(name: str) -> tuple[bool, str]:
    """Check whether an external binary is available, honoring vendored paths."""
    ext = ".exe" if os.name == "nt" else ""

    # 1. Direct vendored executable lookup via TESSERACT_CMD / POPPLER_PATH env vars.
    if name == "tesseract":
        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd and Path(env_cmd).exists():
            return True, env_cmd
    if name in ("pdftotext", "pdfimages", "pdfinfo", "pdftoppm"):
        poppler_path = os.environ.get("POPPLER_PATH")
        if poppler_path:
            candidate = Path(poppler_path) / (name + ext)
            if candidate.exists():
                return True, str(candidate)
            # Some Poppler distributions ship binaries under a bin/ subdirectory.
            candidate_bin = Path(poppler_path) / "bin" / (name + ext)
            if candidate_bin.exists():
                return True, str(candidate_bin)

    # 2. Resolve from PATH / shutil.which.
    path = shutil.which(name)
    if path:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False, f"{name} --version failed"
            output = (result.stdout + result.stderr).strip()
            first_line = output.splitlines()[0] if output.splitlines() else "unknown"
            return True, first_line
        except Exception as exc:
            return False, f"{name} version check failed: {exc}"

    # 3. Project-root vendored fallback (useful in source mode before env vars are set).
    project_root = Path(__file__).resolve().parents[2]
    vendored = project_root / "vendored"
    if name == "tesseract":
        candidate = vendored / "tesseract" / f"tesseract{ext}"
        if candidate.exists():
            return True, str(candidate)
    if name in ("pdftotext", "pdfimages", "pdfinfo", "pdftoppm"):
        candidate = vendored / "poppler" / f"{name}{ext}"
        if candidate.exists():
            return True, str(candidate)
        candidate_bin = vendored / "poppler" / "bin" / f"{name}{ext}"
        if candidate_bin.exists():
            return True, str(candidate_bin)

    return False, f"{name} not found in PATH or vendored layout"


def _sqlite_available(db_path: Optional[Path] = None) -> tuple[bool, str]:
    if db_path is None:
        db_url = os.environ.get("DATABASE_URL", "sqlite:///./taxflow.db")
        if db_url.startswith("sqlite:///"):
            db_path = Path(db_url.replace("sqlite:///", ""))
        else:
            db_path = Path("taxflow.db")
    try:
        # Opening a non-existent SQLite file creates it; limit to temp in-memory
        # probe if the configured path does not exist.
        probe_path = str(db_path) if db_path.exists() else ":memory:"
        conn = sqlite3.connect(probe_path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            return integrity == "ok", f"SQLite integrity check: {integrity}"
        finally:
            conn.close()
    except Exception as exc:
        return False, f"SQLite probe failed: {exc}"


def _model_artifacts_available() -> tuple[bool, str]:
    from ..local.settings import LOCAL_ROOT
    model_dir = LOCAL_ROOT / "ml"
    model_file = model_dir / "local_model.pkl"
    meta_file = model_dir / "model_meta.json"
    if model_file.exists() and meta_file.exists():
        return True, "Local ML model artifacts present"
    if model_file.exists() or meta_file.exists():
        return True, "Partial ML model artifacts present"
    return True, "No local ML model found (optional; train on upload)"


def run_bootstrap(db_path: Optional[Path] = None) -> BootstrapReport:
    """Check all local dependencies required for offline operation."""
    checks: list[BootstrapCheck] = []

    required_modules = [
        ("fastapi", True),
        ("sqlalchemy", True),
        ("cryptography", True),
        ("pdfplumber", True),
        ("PIL", True),
        ("pytesseract", False),
    ]
    for module, required in required_modules:
        available = _module_available(module)
        checks.append(
            BootstrapCheck(
                name=f"module:{module}",
                available=available,
                required=required,
                message=f"{module} is {'available' if available else 'MISSING'}",
            )
        )

    # Optional OCR stack
    ocr_modules = [("pdf2image", True), ("pytesseract", True)]
    ocr_ready = all(_module_available(m) for m, _ in ocr_modules)
    checks.append(
        BootstrapCheck(
            name="ocr_stack",
            available=ocr_ready,
            required=False,
            message="OCR dependencies present" if ocr_ready else "OCR dependencies missing (OCR upload disabled)",
        )
    )

    # External binaries
    for binary, required in [("tesseract", False), ("pdftotext", False), ("pdftoppm", False)]:
        available, msg = _binary_available(binary)
        checks.append(
            BootstrapCheck(
                name=f"binary:{binary}",
                available=available,
                required=required,
                message=msg,
            )
        )

    # SQLite / configured DB
    sqlite_ok, sqlite_msg = _sqlite_available(db_path)
    checks.append(
        BootstrapCheck(
            name="database:sqlite",
            available=sqlite_ok,
            required=True,
            message=sqlite_msg,
        )
    )

    # Local model artifacts (optional)
    model_ok, model_msg = _model_artifacts_available()
    checks.append(
        BootstrapCheck(
            name="ml:model_artifacts",
            available=model_ok,
            required=False,
            message=model_msg,
        )
    )

    ready = all(c.available or not c.required for c in checks)
    return BootstrapReport(ready=ready, checks=checks)


def print_report(report: BootstrapReport) -> None:
    for c in report.checks:
        status = "PASS" if c.available else "FAIL"
        req = " (required)" if c.required else ""
        print(f"[{status}]{req} {c.name}: {c.message}")
    print("Ready:", report.ready)


if __name__ == "__main__":
    report = run_bootstrap()
    print_report(report)
