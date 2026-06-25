#!/usr/bin/env python3
"""Build the Linux portable tarball and AppImage recipe for TaxFlow Pro.

Run from the project root:
    python scripts/build_linux.py

Outputs:
    dist/linux/TaxFlowPro-3.10.0-linux.tar.gz
    dist/linux/AppDir/              -- AppImage staging directory

To produce an actual AppImage, install appimagetool and run:
    cd dist/linux && appimagetool AppDir TaxFlowPro-3.10.0-x86_64.AppImage
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist" / "linux"
BUNDLE_DIR = DIST_DIR / "TaxFlowPro"
APPDIR = DIST_DIR / "AppDir"
VERSION = "3.10.0"


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


def collect_bundle() -> None:
    """Stage a portable directory tree (no PyInstaller needed on Linux)."""
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True)

    # On Linux the launcher falls back to system tesseract/poppler, so the
    # vendored Windows binaries are not required. Still copy them if present.
    items = [
        (PROJECT_ROOT / "backend", BUNDLE_DIR / "backend"),
        (PROJECT_ROOT / "phase3_pipeline", BUNDLE_DIR / "phase3_pipeline"),
        (PROJECT_ROOT / "alembic", BUNDLE_DIR / "alembic"),
        (PROJECT_ROOT / "alembic.ini", BUNDLE_DIR / "alembic.ini"),
        (PROJECT_ROOT / "frontend" / "dist", BUNDLE_DIR / "frontend" / "dist"),
        (PROJECT_ROOT / "vendored", BUNDLE_DIR / "vendored"),
        (PROJECT_ROOT / "requirements.txt", BUNDLE_DIR / "requirements.txt"),
        (PROJECT_ROOT / "version.txt", BUNDLE_DIR / "version.txt"),
        (PROJECT_ROOT / "scripts" / "taxflow_launcher.py", BUNDLE_DIR / "taxflow_launcher.py"),
        (PROJECT_ROOT / "version.txt", BUNDLE_DIR / "version.txt"),
    ]
    for src, dst in items:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Write a shell launcher wrapper.
    wrapper = BUNDLE_DIR / "TaxFlowPro.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        "cd \"$(dirname \"$0\")\" || exit 1\n"
        "exec python3 taxflow_launcher.py \"$@\"\n"
    )
    wrapper.chmod(0o755)


def build_tarball() -> None:
    archive_name = f"TaxFlowPro-{VERSION}-linux.tar.gz"
    archive_path = DIST_DIR / archive_name
    if archive_path.exists():
        archive_path.unlink()
    _run(["tar", "-czf", str(archive_path), "-C", str(DIST_DIR), "TaxFlowPro"])
    print(f"Portable tarball: {archive_path}")


def build_appdir() -> None:
    """Stage an AppDir for appimagetool."""
    if APPDIR.exists():
        shutil.rmtree(APPDIR)
    APPDIR.mkdir(parents=True)

    usr_bin = APPDIR / "usr" / "bin"
    usr_bin.mkdir(parents=True)
    usr_share = APPDIR / "usr" / "share"

    # Copy bundle contents into usr/bin.
    for src in BUNDLE_DIR.iterdir():
        dst = usr_bin / src.name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # AppImage desktop entry and icon stubs.
    (APPDIR / "AppRun").write_text(
        "#!/bin/sh\n"
        "cd \"$(dirname \"$0\")/usr/bin\" || exit 1\n"
        "exec ./TaxFlowPro.sh \"$@\"\n"
    )
    (APPDIR / "AppRun").chmod(0o755)

    desktop = APPDIR / "taxflowpro.desktop"
    desktop.write_text(
        "[Desktop Entry]\n"
        "Name=TaxFlow Pro\n"
        "Exec=TaxFlowPro.sh\n"
        "Icon=taxflowpro\n"
        "Type=Application\n"
        "Categories=Office;Finance;\n"
        "Comment=Local-first tax and accounting pipeline\n"
    )
    # Touch empty icon placeholder.
    (usr_share / "pixmaps").mkdir(parents=True, exist_ok=True)
    (usr_share / "pixmaps" / "taxflowpro.png").write_bytes(b"")

    print(f"AppDir staged: {APPDIR}")
    print("Run: appimagetool AppDir TaxFlowPro-3.10.0-x86_64.AppImage")


def main() -> int:
    if platform.system() != "Linux":
        print("WARNING: Building Linux package on a non-Linux host. AppImage binaries cannot be produced here.")
        print("A portable source tarball can still be generated, but it is not a native executable.")
    print(f"Building TaxFlow Pro {VERSION} for Linux")
    build_frontend()
    collect_bundle()
    build_tarball()
    build_appdir()
    print("Linux build scaffold complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
