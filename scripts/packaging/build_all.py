"""Cross-platform installer build entry point.

Usage:
    python build_all.py [--windows] [--macos] [--linux] [--skip-pyinstaller]

By default it builds the installer for the host OS only.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
from pathlib import Path

from shared import (
    INSTALLER_DIR,
    LAUNCHER_SCRIPT,
    PROJECT_ROOT,
    FRONTEND_DIR,
    VENDORED_DIR,
    VERSION,
    vendored_layout_ok,
    resource_path,
    ensure_version_file,
    frontend_dist_exists,
    fail,
    warn,
)


def _install_scaffold_if_needed() -> None:
    """If Bundles B+C have not produced a launcher, copy the scaffold."""
    if LAUNCHER_SCRIPT.exists():
        return
    scaffold = resource_path("taxflow_launcher_scaffold.py")
    if scaffold.exists():
        warn("launcher script missing; copying scaffold for test builds")
        shutil.copy2(scaffold, LAUNCHER_SCRIPT)
        os.environ.setdefault("TAXFLOW_VERSION", VERSION)
    else:
        fail("launcher scaffold not found")


def _build_windows(skip_pyinstaller: bool) -> int:
    builder = resource_path("windows", "build_windows.py")
    cmd = [sys.executable, str(builder)]
    if skip_pyinstaller:
        cmd.append("--skip-pyinstaller")
    import subprocess
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def _build_macos(skip_pyinstaller: bool) -> int:
    builder = resource_path("macos", "build_macos.py")
    cmd = [sys.executable, str(builder)]
    if skip_pyinstaller:
        cmd.append("--skip-pyinstaller")
    import subprocess
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def _build_linux(skip_pyinstaller: bool) -> int:
    builder = resource_path("linux", "build_linux.py")
    cmd = [sys.executable, str(builder)]
    if skip_pyinstaller:
        cmd.append("--skip-pyinstaller")
    import subprocess
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def _build_frontend() -> None:
    """Run `npm run build` if frontend/dist is missing or stale."""
    dist_index = FRONTEND_DIR / "dist" / "index.html"
    src_dir = FRONTEND_DIR / "src"
    newest_src = max(
        (p.stat().st_mtime for p in [src_dir] if p.exists()), default=0
    )
    if dist_index.exists() and dist_index.stat().st_mtime > newest_src:
        print("[build_all] frontend/dist is up to date")
        return
    npm = shutil.which("npm")
    if not npm:
        fail("npm not found; cannot build frontend")
    result = subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR)
    if result.returncode != 0:
        fail("frontend build failed")


def _wait_for_bundles() -> None:
    """Block until Bundle B+C vendored binaries are present."""
    ok, missing = vendored_layout_ok()
    if not ok:
        warn("waiting for Bundle B+C; missing:\n  - " + "\n  - ".join(missing))
    while not ok:
        import time
        time.sleep(30)
        ok, missing = vendored_layout_ok()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TaxFlow Pro installers")
    parser.add_argument("--windows", action="store_true", help="Build Windows installer")
    parser.add_argument("--macos", action="store_true", help="Build macOS bundle + DMG")
    parser.add_argument("--linux", action="store_true", help="Build Linux package")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Only run installer wrappers, skip PyInstaller")
    parser.add_argument("--force", action="store_true", help="Build even if vendored binaries are missing")
    parser.add_argument("--wait-for-bundles", action="store_true", help="Block until Bundle B+C binaries are present")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend rebuild")
    args = parser.parse_args()

    ensure_version_file()
    if not args.skip_frontend:
        _build_frontend()
    if not frontend_dist_exists():
        fail("frontend/dist/index.html missing; build frontend first")

    _install_scaffold_if_needed()

    if args.wait_for_bundles:
        _wait_for_bundles()

    if not (args.windows or args.macos or args.linux):
        system = platform.system()
        if system == "Windows":
            args.windows = True
        elif system == "Darwin":
            args.macos = True
        elif system == "Linux":
            args.linux = True
        else:
            fail(f"unsupported host OS: {system}")

    ok, missing = vendored_layout_ok()
    if not ok and not args.force and not args.wait_for_bundles:
        fail(
            "vendored layout incomplete:\n  - " + "\n  - ".join(missing)
            + "\nRun with --force to ignore, --wait-for-bundles to wait, or wait for Bundles B+C to finish."
        )
    if not ok:
        warn("vendored binaries missing; continuing with --force (installer may be incomplete)")

    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)

    rc = 0
    if args.windows:
        rc |= _build_windows(args.skip_pyinstaller)
    if args.macos:
        rc |= _build_macos(args.skip_pyinstaller)
    if args.linux:
        rc |= _build_linux(args.skip_pyinstaller)

    return rc


if __name__ == "__main__":
    sys.exit(main())
