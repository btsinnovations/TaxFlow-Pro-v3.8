"""Shared constants and helpers for TaxFlow Pro packaging.

All build scripts import this module. It defines:
- canonical version / naming
- per-platform user-data directories
- required vendored binary layout
- artifact output paths
- small helper utilities for copying assets and validating layout
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Canonical metadata
# ---------------------------------------------------------------------------

VERSION = "3.11.5"
APP_NAME = "TaxFlow Pro"
APP_IDENTIFIER = "com.taxflowpro.app"
COPYRIGHT = "Copyright (c) TaxFlow Pro contributors"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
ALEMBIC_DIR = PROJECT_ROOT / "alembic"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
VERSION_FILE = PROJECT_ROOT / "version.txt"

# Launcher created by Bundles B+C
LAUNCHER_SCRIPT = PROJECT_ROOT / "scripts" / "taxflow_launcher.py"
VENDORED_DIR = PROJECT_ROOT / "vendored"
TESSERACT_DIR = VENDORED_DIR / "tesseract"
POPPLER_DIR = VENDORED_DIR / "poppler"

# ---------------------------------------------------------------------------
# Output layout
# ---------------------------------------------------------------------------

DIST_ROOT = PROJECT_ROOT / "dist"
INSTALLER_DIR = DIST_ROOT / "installers"
PYINSTALLER_DIR = DIST_ROOT / "pyinstaller"

# ---------------------------------------------------------------------------
# Per-platform local data directories (outside install dir)
# ---------------------------------------------------------------------------


def local_data_root() -> Path:
    """Return the platform-specific user-writable data directory."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = Path.home() / "AppData" / "Local"
        return Path(base) / "TaxFlowPro"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "TaxFlowPro"
    return Path.home() / ".local" / "share" / "TaxFlowPro"


# ---------------------------------------------------------------------------
# Vendored binary detection
# ---------------------------------------------------------------------------


def binary_extension() -> str:
    return ".exe" if platform.system() == "Windows" else ""


def find_vendored_tesseract() -> Path | None:
    exe = TESSERACT_DIR / f"tesseract{binary_extension()}"
    return exe if exe.exists() else None


def find_vendored_poppler() -> Path | None:
    exe = POPPLER_DIR / f"pdftotext{binary_extension()}"
    return exe if exe.exists() else None


def vendored_layout_ok() -> tuple[bool, list[str]]:
    """Validate that vendored binaries required by the launcher exist."""
    missing: list[str] = []
    if not LAUNCHER_SCRIPT.exists():
        missing.append(f"launcher script: {LAUNCHER_SCRIPT}")
    if not find_vendored_tesseract():
        missing.append(f"tesseract binary: {TESSERACT_DIR / ('tesseract' + binary_extension())}")
    if not find_vendored_poppler():
        missing.append(f"poppler binary: {POPPLER_DIR / ('pdftotext' + binary_extension())}")
    # Tessdata is required for OCR to recognize text.
    tessdata = TESSERACT_DIR / "tessdata"
    if not tessdata.exists() or not any(tessdata.iterdir()):
        missing.append(f"tessdata directory: {tessdata}")
    ok = not missing
    return ok, missing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_version_file() -> None:
    """Make sure version.txt matches the packaging VERSION constant."""
    if VERSION_FILE.exists() and VERSION_FILE.read_text().strip() == VERSION:
        return
    VERSION_FILE.write_text(VERSION + "\n")


def read_version_from_file() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return VERSION


def copytree_ignore(src: Path, names: list[str]) -> set[str]:
    """shutil.copytree ignore callable: drop Python caches and node_modules."""
    ignore: set[str] = set()
    for name in names:
        if name in {"__pycache__", ".pytest_cache", "node_modules", ".git", ".venv", "venv"}:
            ignore.add(name)
        if name.endswith(".pyc") or name.endswith(".pyo"):
            ignore.add(name)
        if name == ".DS_Store":
            ignore.add(name)
    return ignore


def copy_source_tree(src: Path, dst: Path) -> None:
    """Copy a source tree to a staging area, ignoring build artifacts."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=copytree_ignore)


def run(cmd: list[str | Path], cwd: Path | None = None, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return CompletedProcess, with friendly error handling."""
    cmd_str = [str(c) for c in cmd]
    print(f"[run] {' '.join(cmd_str)}")
    return subprocess.run(cmd_str, cwd=cwd, check=check, **kwargs)


def detect_7zip() -> Path | None:
    """Return path to 7z if available (used for NSIS/ZIP if needed)."""
    for name in ("7z", "7za", "7zz"):
        path = shutil.which(name)
        if path:
            return Path(path)
    common = Path(r"C:\Program Files\7-Zip\7z.exe")
    if common.exists():
        return common
    return None


def resource_path(*parts: str) -> Path:
    """Return a path under scripts/packaging/."""
    return Path(__file__).resolve().parent / Path(*parts)


def frontend_dist_exists() -> bool:
    return (FRONTEND_DIR / "dist" / "index.html").exists()


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def warn(message: str) -> None:
    print(f"WARN: {message}", file=sys.stderr)
