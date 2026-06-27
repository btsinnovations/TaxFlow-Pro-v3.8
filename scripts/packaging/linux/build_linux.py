"""Linux packaging build for TaxFlow Pro.

Produces:
- dist/pyinstaller/TaxFlowPro/              (onedir bundle)
- dist/installers/TaxFlowPro-3.10.0-linux.tar.gz   (portable tarball)
- dist/installers/TaxFlowPro-3.10.0-x86_64.AppImage (if appimagetool is available)

Data directory: ~/.local/share/TaxFlowPro
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import (
    APP_NAME,
    VERSION,
    PROJECT_ROOT,
    ALEMBIC_DIR,
    FRONTEND_DIR,
    VENDORED_DIR,
    LAUNCHER_SCRIPT,
    DIST_ROOT,
    INSTALLER_DIR,
    PYINSTALLER_DIR,
    resource_path,
    fail,
    warn,
)

BUNDLE_NAME = "TaxFlowPro"
BUNDLE_DIR = PYINSTALLER_DIR / BUNDLE_NAME
TARBALL_NAME = f"TaxFlowPro-{VERSION}-linux.tar.gz"
APPIMAGE_NAME = f"TaxFlowPro-{VERSION}-x86_64.AppImage"
ICON_PATH = resource_path("assets", "icon.svg")
APPRUN_PATH = resource_path("linux", "AppRun")
DESKTOP_PATH = resource_path("linux", "taxflowpro.desktop")
RUN_WRAPPER = resource_path("linux", "run.sh")


def _pyinstaller_available() -> bool:
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _create_icon() -> None:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([32, 32, 480, 480], radius=64, fill=(0, 112, 240, 255))
        draw.text((256, 256), "TFP", fill="white", anchor="mm")
        sizes = [16, 32, 48, 64, 128, 256, 512]
        for s in sizes:
            img.resize((s, s), Image.LANCZOS).save(ICON_PATH.parent / f"icon_{s}.png")
        img.save(ICON_PATH)
    except Exception as exc:
        warn(f"could not generate icon: {exc}")


def _write_spec() -> Path:
    if not ICON_PATH.exists():
        _create_icon()
    spec_path = resource_path("linux", "TaxFlowPro_linux.spec")
    content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from pathlib import Path

root = Path(r"{PROJECT_ROOT}")

added_files = [
    (str(root / "frontend" / "dist"), "frontend/dist"),
    (str(root / "alembic"), "alembic"),
    (str(root / "alembic.ini"), "."),
    (str(root / "version.txt"), "."),
    (str(root / "requirements.txt"), "."),
    (str(root / "categories.yaml"), "."),
    (str(root / "scripts" / "taxflow_launcher.py"), "scripts/taxflow_launcher.py"),
    (str(root / "scripts" / "backup.py"), "scripts/backup.py"),
    (str(root / "scripts" / "restore.py"), "scripts/restore.py"),
]

vendored = root / "vendored"
if vendored.exists():
    for sub in vendored.iterdir():
        if sub.is_dir():
            added_files.append((str(sub), f"vendored/{{sub.name}}"))

ml = root / "ml"
if ml.exists():
    added_files.append((str(ml), "ml"))

a = Analysis(
    [str(root / "scripts" / "packaging" / "launcher_adapter.py")],
    pathex=[str(root), str(root / "scripts"), str(root / "scripts" / "packaging")],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.workers",
        "fastapi",
        "fastapi.staticfiles",
        "starlette.staticfiles",
        "starlette.responses",
        "sqlalchemy",
        "alembic",
        "backend.api",
        "backend.database",
        "backend.local.settings",
        "backend.local.secrets_loader",
        "backend.local.backup",
        "backend.local.migration_health",
        "backend.local.bootstrap",
        "backend.local.sqlcipher_engine",
        "backend.local.offline",
        "backend.local.ml_pipeline",
        "backend.local.yaml_safe",
        "backend.local.column_encryption",
        "backend.local.crypto",
        "backend.local.keyring_secret",
        "backend.local.security_random",
        "backend.local.guards",
        "backend.rls",
        "backend.audit.append_only",
        "backend.auth",
        "backend.auth_rate_limit",
        "backend.rate_limit",
        "backend.routers.auth",
        "backend.routers.accounts",
        "backend.routers.clients",
        "backend.routers.transactions",
        "backend.routers.coa",
        "backend.routers.profiles",
        "backend.routers.recurring",
        "backend.routers.upload",
        "backend.routers.export",
        "backend.routers.dashboard",
        "backend.routers.tax",
        "backend.routers.ml",
        "backend.routers.audit",
        "backend.routers.depreciation",
        "backend.routers.rules",
        "backend.routers.flags",
        "backend.routers.gl",
        "backend.routers.health",
        "backend.routers.tests",
        "backend.parsers.institution",
        "backend.parsers.sandbox",
        "backend.parsers.pdf_guard",
        "backend.services.export",
        "backend.services.flags",
        "backend.services.rules",
        "backend.services.depreciation",
        "backend.security.path_safety",
        "backend.security.request_validation",
        "backend.security.upload_validator",
        "backend.utils.temp_file_cleanup",
        "pandas",
        "pyarrow",
        "joblib",
        "sklearn",
        "sklearn.feature_extraction.text",
        "sklearn.linear_model",
        "sklearn.model_selection",
        "sklearn.metrics",
        "sklearn.pipeline",
        "pytesseract",
        "pdf2image",
        "PIL",
        "pdfplumber",
        "fpdf",
        "openpyxl",
        "cryptography",
        "keyring",
        "PyPDF2",
        "jose",
        "jose.backends",
        "bcrypt",
        "dotenv",
        "sqlcipher3.dbapi2",
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="{BUNDLE_NAME}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="{BUNDLE_NAME}",
)
'''
    spec_path.write_text(content, encoding="utf-8")
    return spec_path


def _run_pyinstaller() -> None:
    if not _pyinstaller_available():
        fail("PyInstaller not available; install with `pip install pyinstaller`")
    spec = _write_spec()
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec),
    ]
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def _write_desktop_file() -> None:
    content = f'''[Desktop Entry]
Name={APP_NAME}
Comment=Local-first tax document processing
Exec=%k/TaxFlowPro
Icon=%k/icon_256.png
Type=Application
Terminal=false
Categories=Office;Finance;
'''
    DESKTOP_PATH.write_text(content, encoding="utf-8")


def _write_apprun() -> None:
    content = f'''#!/bin/sh
# AppImage entry point for {APP_NAME} {VERSION}
set -e
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE:$PATH"
exec "$HERE/TaxFlowPro" "$@"
'''
    APPRUN_PATH.write_text(content, encoding="utf-8")
    APPRUN_PATH.chmod(APPRUN_PATH.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_run_wrapper() -> None:
    content = f'''#!/bin/sh
# Launch {APP_NAME} {VERSION} from extracted tarball
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HERE:$PATH"
exec "$HERE/TaxFlowPro" "$@"
'''
    RUN_WRAPPER.write_text(content, encoding="utf-8")
    RUN_WRAPPER.chmod(RUN_WRAPPER.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _build_tarball() -> None:
    tarball = INSTALLER_DIR / TARBALL_NAME
    if tarball.exists():
        tarball.unlink()
    _write_desktop_file()
    _write_run_wrapper()
    shutil.copy2(DESKTOP_PATH, BUNDLE_DIR / "taxflowpro.desktop")
    shutil.copy2(RUN_WRAPPER, BUNDLE_DIR / "run.sh")
    # Copy icon PNGs if generated.
    for png in ICON_PATH.parent.glob("icon_*.png"):
        shutil.copy2(png, BUNDLE_DIR / png.name)
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(BUNDLE_DIR, arcname=BUNDLE_NAME)
    print(f"[linux] tarball produced: {tarball}")


def _build_appimage() -> None:
    tool = shutil.which("appimagetool")
    if not tool:
        warn("appimagetool not found; AppImage not produced")
        return
    appdir = DIST_ROOT / "TaxFlowPro.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    shutil.copytree(BUNDLE_DIR, appdir)
    _write_apprun()
    _write_desktop_file()
    shutil.copy2(APPRUN_PATH, appdir / "AppRun")
    shutil.copy2(DESKTOP_PATH, appdir / "taxflowpro.desktop")
    for png in ICON_PATH.parent.glob("icon_*.png"):
        shutil.copy2(png, appdir / png.name)
    # AppImage uses .DirIcon symlink to 256px icon
    target = appdir / "icon_256.png"
    if target.exists():
        (appdir / ".DirIcon").symlink_to(target.name)
    output = INSTALLER_DIR / APPIMAGE_NAME
    env = os.environ.copy()
    env.setdefault("ARCH", "x86_64")
    subprocess.run([tool, str(appdir), str(output)], check=True, cwd=PROJECT_ROOT, env=env)
    output.chmod(output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"[linux] AppImage produced: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TaxFlow Pro Linux package")
    parser.add_argument("--skip-pyinstaller", action="store_true")
    parser.add_argument("--appimage", action="store_true")
    args = parser.parse_args()

    if not args.skip_pyinstaller:
        _run_pyinstaller()
    else:
        if not BUNDLE_DIR.exists():
            fail(f"--skip-pyinstaller requested but {BUNDLE_DIR} does not exist")

    _build_tarball()
    if args.appimage:
        _build_appimage()
    return 0


if __name__ == "__main__":
    sys.exit(main())
