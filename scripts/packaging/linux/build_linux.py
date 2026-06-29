#!/usr/bin/env python3
"""Linux .deb build script for TaxFlow Pro.

Builds a PyInstaller bundle and wraps it in a .deb package.

Trust signals (B7.03):
  - Baseline: unsigned .deb, users verify GPG signature manually
  - Stage 2: set TAXFLOW_GPG_KEY_ID env var to sign the .deb
  - Stage 3: PPA/Flatpak publication (future)

Usage:
    python build_linux.py

Environment variables (all optional):
    TAXFLOW_GPG_KEY_ID — GPG key ID for signing the .deb
    PYINSTALLER_ARGS   — Extra args passed to PyInstaller
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

VERSION = "3.11.6"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = PROJECT_ROOT / "dist"
DEB_ROOT = BUILD_DIR / "deb-staging"


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"[linux-build] {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def build_pyinstaller() -> int:
    spec_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "TaxFlowPro",
        "--windowed",
        "--onedir",
        "--add-data", f"{PROJECT_ROOT}/backend:backend",
        "--add-data", f"{PROJECT_ROOT}/frontend/dist:frontend_dist",
        "--add-data", f"{PROJECT_ROOT}/alembic:alembic",
        "--add-data", f"{PROJECT_ROOT}/alembic.ini:.",
    ]
    extra = os.environ.get("PYINSTALLER_ARGS", "")
    if extra:
        spec_args.extend(extra.split())
    spec_args.append(str(PROJECT_ROOT / "scripts/taxflow_launcher.py"))
    return run(spec_args, cwd=PROJECT_ROOT)


def build_deb() -> int:
    import shutil
    if DEB_ROOT.exists():
        shutil.rmtree(DEB_ROOT)

    # Create .deb directory structure
    pkg_dir = DEB_ROOT / "taxflow-pro" / f"_{VERSION}_amd64"
    (pkg_dir / "opt" / "taxflow-pro").mkdir(parents=True, exist_ok=True)
    (pkg_dir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (pkg_dir / "DEBIAN").mkdir(parents=True, exist_ok=True)

    # Copy PyInstaller output
    pyinstaller_out = BUILD_DIR / "TaxFlowPro"
    if pyinstaller_out.exists():
        shutil.copytree(pyinstaller_out, pkg_dir / "opt" / "taxflow-pro", dirs_exist_ok=True)

    # Symlink /usr/bin/taxflow-pro -> /opt/taxflow-pro/TaxFlowPro
    bin_link = pkg_dir / "usr" / "bin" / "taxflow-pro"
    bin_link.symlink_to("/opt/taxflow-pro/TaxFlowPro")

    # Control file
    control = pkg_dir / "DEBIAN" / "control"
    control.write_text(f"""Package: taxflow-pro
Version: {VERSION}
Section: office
Priority: optional
Architecture: amd64
Depends: libgl1, libegl1, libxkbcommon0
Maintainer: BTS Innovations <support@btsinnovations.com>
Description: TaxFlow Pro — Local-first bookkeeping platform
 TaxFlow Pro is a privacy-first bookkeeping and tax preparation
 application that stores all data locally on your machine.
""", encoding="utf-8")

    # Build .deb
    deb_path = BUILD_DIR / f"taxflow-pro_{VERSION}_amd64.deb"
    ret = run(["dpkg-deb", "--build", str(pkg_dir), str(deb_path)])
    if ret != 0:
        print("[linux-build] dpkg-deb failed", file=sys.stderr)
        return ret

    # Sign if GPG key provided
    gpg_key = os.environ.get("TAXFLOW_GPG_KEY_ID")
    if gpg_key:
        ret = run(["dpkg-sig", "--sign", "builder", "-k", gpg_key, str(deb_path)])
        if ret != 0:
            print("[linux-build] GPG signing failed", file=sys.stderr)
    else:
        print("[linux-build] TAXFLOW_GPG_KEY_ID not set — skipping signing")

    print(f"[linux-build] .deb created at {deb_path}")
    return 0


def main() -> int:
    print(f"[linux-build] Building TaxFlow Pro v{VERSION}")
    ret = build_pyinstaller()
    if ret != 0:
        return ret
    ret = build_deb()
    if ret != 0:
        return ret
    print("[linux-build] Build complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())