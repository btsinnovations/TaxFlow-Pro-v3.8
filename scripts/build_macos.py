#!/usr/bin/env python3
"""Build the macOS `.app` bundle and `.dmg` for TaxFlow Pro.

Run from the project root on a Mac:
    python scripts/build_macos.py

Outputs:
    dist/macos/TaxFlowPro.app/
    dist/macos/TaxFlowPro-3.10.0.dmg

Requires macOS. Cannot be produced on Windows/Linux without a cross-build
environment.
"""

from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist" / "macos"
APP_DIR = DIST_DIR / "TaxFlowPro.app"
CONTENTS = APP_DIR / "Contents"
RESOURCES = CONTENTS / "Resources"
MACOS_DIR = CONTENTS / "MacOS"
VERSION = "3.10.0"
BUNDLE_ID = "com.faircashinvestments.taxflowpro"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=True)


def build_frontend() -> None:
    frontend = PROJECT_ROOT / "frontend"
    node_modules = frontend / "node_modules"
    npm_cmd = "npm"
    if platform.system() == "Windows":
        npm_cmd = "npm.cmd"
    if not node_modules.exists():
        _run([npm_cmd, "install"], cwd=frontend)
    _run([npm_cmd, "run", "build"], cwd=frontend)


def build_app() -> None:
    """Stage the .app bundle structure."""
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    CONTENTS.mkdir(parents=True)
    RESOURCES.mkdir(parents=True)
    MACOS_DIR.mkdir(parents=True)

    # Copy backend code and vendored binaries into Resources.
    items = [
        (PROJECT_ROOT / "backend", RESOURCES / "backend"),
        (PROJECT_ROOT / "phase3_pipeline", RESOURCES / "phase3_pipeline"),
        (PROJECT_ROOT / "alembic", RESOURCES / "alembic"),
        (PROJECT_ROOT / "alembic.ini", RESOURCES / "alembic.ini"),
        (PROJECT_ROOT / "frontend" / "dist", RESOURCES / "frontend" / "dist"),
        (PROJECT_ROOT / "vendored", RESOURCES / "vendored"),
        (PROJECT_ROOT / "requirements.txt", RESOURCES / "requirements.txt"),
        (PROJECT_ROOT / "scripts" / "taxflow_launcher.py", RESOURCES / "taxflow_launcher.py"),
        (PROJECT_ROOT / "version.txt", RESOURCES / "version.txt"),
    ]
    for src, dst in items:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # macOS executable wrapper.
    wrapper = MACOS_DIR / "TaxFlowPro"
    wrapper.write_text(
        "#!/bin/sh\n"
        "cd \"$(dirname \"$0\")/../Resources\" || exit 1\n"
        "exec python3 taxflow_launcher.py \"$@\"\n"
    )
    wrapper.chmod(0o755)

    # Info.plist.
    plist = {
        "CFBundleName": "TaxFlow Pro",
        "CFBundleDisplayName": "TaxFlow Pro",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "CFBundleExecutable": "TaxFlowPro",
        "CFBundlePackageType": "APPL",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
    }
    with open(CONTENTS / "Info.plist", "wb") as f:
        plistlib.dump(plist, f)

    print(f".app bundle staged: {APP_DIR}")


def build_dmg() -> None:
    """Create a .dmg image from the .app bundle.

    Uses `create-dmg` if available; otherwise falls back to hdiutil.
    """
    dmg_path = DIST_DIR / f"TaxFlowPro-{VERSION}.dmg"
    if dmg_path.exists():
        dmg_path.unlink()

    create_dmg = shutil.which("create-dmg")
    if create_dmg:
        _run([
            create_dmg,
            "--volname", "TaxFlow Pro Installer",
            "--window-pos", "200", "120",
            "--window-size", "800", "400",
            "--icon-size", "100",
            "--app-drop-link", "600", "185",
            str(dmg_path),
            str(APP_DIR),
        ], cwd=DIST_DIR)
    else:
        # hdiutil fallback: temporary read/write image, copy app, convert.
        tmp_dmg = DIST_DIR / "TaxFlowPro-tmp.dmg"
        _run([
            "hdiutil", "create", "-srcfolder", str(APP_DIR),
            "-volname", "TaxFlow Pro Installer",
            "-fs", "HFS+", "-size", "200m",
            str(tmp_dmg), "-ov", "-format", "UDRW",
        ])
        _run([
            "hdiutil", "convert", str(tmp_dmg),
            "-format", "UDZO", "-o", str(dmg_path),
        ])
        tmp_dmg.unlink()

    print(f".dmg image: {dmg_path}")


def main() -> int:
    if platform.system() != "Darwin":
        print("WARNING: Building macOS .app on a non-macOS host. Native binaries cannot be produced here.")
        print("A source-only bundle can still be scaffolded, but it is not a runnable .app on macOS.")
    print(f"Building TaxFlow Pro {VERSION} for macOS")
    build_frontend()
    build_app()
    if platform.system() == "Darwin":
        build_dmg()
    else:
        print("Skipping .dmg creation — requires macOS host.")
    print("macOS build scaffold complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
