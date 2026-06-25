#!/usr/bin/env python3
"""Build the Windows PyInstaller bundle and Inno Setup installer.

Run from the project root:
    python scripts/build_windows.py

Outputs:
    dist/pyinstaller/TaxFlowPro/     -- one-dir bundle
    dist/installer/TaxFlowPro-3.10.0-Setup.exe
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
PYINSTALLER_DIR = DIST_DIR / "pyinstaller" / "TaxFlowPro"
INSTALLER_DIR = DIST_DIR / "installer"
VENDOR_DIR = PROJECT_ROOT / "vendored"

VERSION = "3.10.0"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=True)


def build_frontend() -> None:
    frontend = PROJECT_ROOT / "frontend"
    node_modules = frontend / "node_modules"
    npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
    if not node_modules.exists():
        _run([npm_cmd, "install"], cwd=frontend)
    _run([npm_cmd, "run", "build"], cwd=frontend)


def collect_vendored() -> None:
    """Ensure vendored binaries are staged for PyInstaller."""
    if not (VENDOR_DIR / "poppler").exists():
        raise RuntimeError("vendored/poppler is missing. Run scripts/vendor_binaries.py first.")
    if not (VENDOR_DIR / "tesseract" / "tesseract.exe").exists():
        print("WARNING: vendored/tesseract/tesseract.exe is missing. Installer will lack OCR.")


def build_pyinstaller() -> None:
    """Build the one-dir PyInstaller bundle."""
    if PYINSTALLER_DIR.exists():
        shutil.rmtree(PYINSTALLER_DIR)
    PYINSTALLER_DIR.parent.mkdir(parents=True, exist_ok=True)

    spec = PROJECT_ROOT / "scripts" / "TaxFlowPro.spec"
    if spec.exists():
        _run([sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm", "--clean"])
    else:
        # Use the launcher as the entry point.
        # Collect all project packages so the bundle can import them.
        collect_args = []
        for pkg in ("backend", "phase3_pipeline", "scripts"):
            pkg_path = PROJECT_ROOT / pkg
            if pkg_path.exists():
                collect_args += ["--collect-all", pkg]

        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name", "TaxFlowPro",
            "--onedir",
            "--noconfirm",
            "--clean",
            "--add-data", f"{PROJECT_ROOT / 'alembic'};alembic",
            "--add-data", f"{PROJECT_ROOT / 'alembic.ini'};.",
            "--add-data", f"{PROJECT_ROOT / 'frontend' / 'dist'};frontend/dist",
            "--add-data", f"{PROJECT_ROOT / 'version.txt'};.",
            "--add-data", f"{VENDOR_DIR};vendored",
        ] + collect_args + [
            str(PROJECT_ROOT / "scripts" / "taxflow_launcher.py"),
        ]
        _run(cmd)


def build_installer() -> None:
    """Build the Windows installer with Inno Setup if available."""
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    iss = PROJECT_ROOT / "scripts" / "installer_windows.iss"

    # Find Inno Setup compiler.
    iscc_candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
    ]
    iscc = next((c for c in iscc_candidates if c.exists()), None)
    if not iscc:
        print("WARNING: Inno Setup compiler (ISCC.exe) not found. Skipping .exe installer build.")
        print("Install Inno Setup 6 from https://jrsoftware.org/isinfo.php and rerun.")
        return

    _run([str(iscc), str(iss)], cwd=iss.parent)


def main() -> int:
    print(f"Building TaxFlow Pro {VERSION} for Windows")
    build_frontend()
    collect_vendored()
    build_pyinstaller()
    build_installer()
    print("Build complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
