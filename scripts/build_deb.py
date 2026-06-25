#!/usr/bin/env python3
"""Build an Ubuntu/Debian .deb package for TaxFlow Pro.

Run on Ubuntu from the project root:
    python3 scripts/build_deb.py

Output:
    dist/deb/taxflow-pro_3.10.0_amd64.deb

The package declares dependencies on Python 3, tesseract-ocr, poppler-utils, and
python3-venv. It ships its own virtual environment at /opt/taxflow-pro/.venv
so it never touches the system Python site-packages.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist" / "deb"
STAGE_DIR = DIST_DIR / "stage"
PKG_ROOT = STAGE_DIR / "taxflow-pro_3.10.0_amd64"
OPT_DIR = PKG_ROOT / "opt" / "taxflow-pro"
BIN_DIR = PKG_ROOT / "usr" / "local" / "bin"
DEBIAN = PKG_ROOT / "DEBIAN"
VERSION = "3.10.0"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, check=True)


def build_frontend() -> None:
    frontend = PROJECT_ROOT / "frontend"
    node_modules = frontend / "node_modules"
    if not node_modules.exists():
        _run(["npm", "install"], cwd=frontend)
    _run(["npm", "run", "build"], cwd=frontend)


def collect_package() -> None:
    if PKG_ROOT.exists():
        shutil.rmtree(PKG_ROOT)
    OPT_DIR.mkdir(parents=True)
    BIN_DIR.mkdir(parents=True)
    DEBIAN.mkdir(parents=True)

    items = [
        (PROJECT_ROOT / "backend", OPT_DIR / "backend"),
        (PROJECT_ROOT / "phase3_pipeline", OPT_DIR / "phase3_pipeline"),
        (PROJECT_ROOT / "alembic", OPT_DIR / "alembic"),
        (PROJECT_ROOT / "alembic.ini", OPT_DIR / "alembic.ini"),
        (PROJECT_ROOT / "frontend" / "dist", OPT_DIR / "frontend" / "dist"),
        (PROJECT_ROOT / "requirements.txt", OPT_DIR / "requirements.txt"),
        (PROJECT_ROOT / "scripts" / "taxflow_launcher.py", OPT_DIR / "taxflow_launcher.py"),
        (PROJECT_ROOT / "scripts" / "setup_linux.sh", OPT_DIR / "setup_linux.sh"),
        (PROJECT_ROOT / "version.txt", OPT_DIR / "version.txt"),
    ]
    vendored = PROJECT_ROOT / "vendored"
    if vendored.exists():
        items.append((vendored, OPT_DIR / "vendored"))
    for src, dst in items:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Create the bundled venv inside the package. This is built on the
    # packaging host and bundled into the .deb. Using --without-pip avoids
    # depending on the exact pip version available on the host.
    venv = OPT_DIR / ".venv"
    _run(["python3", "-m", "venv", str(venv), "--without-pip"])
    # Ensure pip is available so we can install requirements.
    _run([str(venv / "bin" / "python"), "-m", "ensurepip", "--upgrade"])
    _run([str(venv / "bin" / "pip"), "install", "--upgrade", "pip"])
    _run([str(venv / "bin" / "pip"), "install", "-r", str(OPT_DIR / "requirements.txt")])

    # Wrapper script uses the bundled venv.
    wrapper = BIN_DIR / "taxflow-pro"
    wrapper.write_text(
        "#!/bin/sh\n"
        "cd /opt/taxflow-pro || exit 1\n"
        "exec /opt/taxflow-pro/.venv/bin/python3 taxflow_launcher.py \"$@\"\n"
    )
    wrapper.chmod(0o755)


def write_control() -> None:
    control = DEBIAN / "control"
    control.write_text(
        "Package: taxflow-pro\n"
        "Version: 3.10.0\n"
        "Section: office\n"
        "Priority: optional\n"
        "Architecture: amd64\n"
        "Depends: python3 (>= 3.10), python3-venv, tesseract-ocr, poppler-utils, libsqlite3-0\n"
        "Maintainer: BTS Innovations <support@btsinnovations.com>\n"
        "Description: TaxFlow Pro - local-first tax and accounting pipeline\n"
        " Offline-first desktop app for tax and accounting workflow automation.\n"
    )

    postinst = DEBIAN / "postinst"
    postinst.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        "# User data directory is created at first run by the launcher.\n"
        "exit 0\n"
    )
    postinst.chmod(0o755)

    prerm = DEBIAN / "prerm"
    prerm.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        "# TaxFlow Pro uninstaller - user data in ~/.local/share/TaxFlowPro is preserved.\n"
        "exit 0\n"
    )
    prerm.chmod(0o755)


def build_deb() -> None:
    deb_file = DIST_DIR / f"taxflow-pro_{VERSION}_amd64.deb"
    if deb_file.exists():
        deb_file.unlink()
    _run(["dpkg-deb", "--build", "--root-owner-group", str(PKG_ROOT)], cwd=DIST_DIR)
    built = STAGE_DIR / f"taxflow-pro_{VERSION}_amd64.deb"
    if built.exists():
        built.rename(deb_file)
    print(f".deb package: {deb_file}")


def main() -> int:
    if sys.platform != "linux":
        print("WARNING: .deb packaging should be run on a Debian/Ubuntu host.")
        print("Files will be staged, but dpkg-deb may not be available.")

    for tool in ("dpkg-deb",):
        if shutil.which(tool) is None:
            print(f"ERROR: {tool} not found. Install with: sudo apt install -y dpkg-dev")
            return 1

    build_frontend()
    collect_package()
    write_control()
    build_deb()
    print(".deb build complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
