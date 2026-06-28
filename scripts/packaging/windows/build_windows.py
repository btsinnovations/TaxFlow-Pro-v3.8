#!/usr/bin/env python3
"""Windows build script for TaxFlow Pro.

Builds a PyInstaller one-dir bundle and optionally signs the executable.

Trust signals (B7.03):
  - Baseline: unsigned .exe, users click "Run anyway" on SmartScreen
  - Stage 2: set TAXFLOW_SIGNING_CERT and TAXFLOW_SIGNING_PASSWORD env vars
    to sign with an OV certificate
  - Stage 3: EV certificate for immediate SmartScreen trust (future)

Usage:
    python build_windows.py

Environment variables (all optional):
    TAXFLOW_SIGNING_CERT    — Path to .pfx code-signing certificate
    TAXFLOW_SIGNING_PASSWORD — Password for the certificate
    PYINSTALLER_ARGS        — Extra args passed to PyInstaller
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VERSION = "3.11.6"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = PROJECT_ROOT / "dist"


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"[win-build] {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def build_pyinstaller() -> int:
    spec_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "TaxFlowPro",
        "--windowed",
        "--onedir",
        "--add-data", f"{PROJECT_ROOT}\\backend;backend",
        "--add-data", f"{PROJECT_ROOT}\\frontend\\dist;frontend_dist",
        "--add-data", f"{PROJECT_ROOT}\\alembic;alembic",
        "--add-data", f"{PROJECT_ROOT}\\alembic.ini;.",
    ]
    extra = os.environ.get("PYINSTALLER_ARGS", "")
    if extra:
        spec_args.extend(extra.split())
    spec_args.append(str(PROJECT_ROOT / "scripts/taxflow_launcher.py"))
    return run(spec_args, cwd=PROJECT_ROOT)


def sign_executable() -> int:
    cert = os.environ.get("TAXFLOW_SIGNING_CERT")
    if not cert:
        print("[win-build] TAXFLOW_SIGNING_CERT not set — skipping signing")
        return 0

    password = os.environ.get("TAXFLOW_SIGNING_PASSWORD", "")
    exe_path = BUILD_DIR / "TaxFlowPro" / "TaxFlowPro.exe"

    cmd = [
        "signtool", "sign", "/f", cert,
        "/p", password,
        "/t", "http://timestamp.digicert.com",
        str(exe_path),
    ]
    ret = run(cmd)
    if ret != 0:
        print("[win-build] signtool failed", file=sys.stderr)
    return ret


def main() -> int:
    print(f"[win-build] Building TaxFlow Pro v{VERSION}")
    ret = build_pyinstaller()
    if ret != 0:
        return ret
    ret = sign_executable()
    if ret != 0:
        return ret
    print("[win-build] Build complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())