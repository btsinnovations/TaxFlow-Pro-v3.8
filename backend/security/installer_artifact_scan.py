"""Installer artifact secret-scanning helper.

Stub for v3.11.5 (SEC.26 / SEC.27). This module will eventually:
- Inspect built Windows `.exe`, Linux `.deb`, and macOS `.dmg` artifacts.
- Search for leaked `.env`, `.local_secret`, test fixtures, and private keys.
- Return a pass/fail report suitable for CI gating.

No real scanning is performed yet; importing this module should not fail.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def scan_artifact(path: Path) -> dict:
    """Return a scan report dict for a single installer artifact.

    Keys:
      - path: the artifact path
      - scanned: False until full logic is implemented
      - findings: list of detected issues (empty in stub)
      - passed: True in stub
    """
    return {
        "path": str(path),
        "scanned": False,
        "findings": [],
        "passed": True,
    }


def scan_installer_dir(directory: Path) -> list[dict]:
    """Scan all supported installer artifacts under ``directory``."""
    if not directory.exists():
        return []
    reports: list[dict] = []
    for ext in (".exe", ".deb", ".dmg", ".tar.gz", ".zip"):
        for artifact in directory.glob(f"*{ext}"):
            reports.append(scan_artifact(artifact))
    return reports
