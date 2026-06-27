"""macOS packaging build for TaxFlow Pro.

Produces:
- dist/pyinstaller/TaxFlowPro.app     (bundled .app)
- dist/installers/TaxFlowPro-3.10.0.dmg (if create-dmg is available)

Signing: unsigned by default. Set CODE_SIGN_IDENTITY env var to enable signing.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import (
    APP_NAME,
    APP_IDENTIFIER,
    COPYRIGHT,
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

BUNDLE_NAME = "TaxFlowPro.app"
BUNDLE_DIR = PYINSTALLER_DIR / BUNDLE_NAME
INSTALLER_NAME = f"TaxFlowPro-{VERSION}.dmg"
ICON_PATH = resource_path("assets", "icon.icns")
INFO_PLIST = resource_path("macos", "Info.plist")


def _pyinstaller_available() -> bool:
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _create_icns() -> None:
    """Generate a simple ICNS icon if one doesn't exist."""
    try:
        from PIL import Image, ImageDraw
        sizes = [16, 32, 64, 128, 256, 512]
        iconset = ICON_PATH.with_suffix(".iconset")
        iconset.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([64, 64, 960, 960], radius=128, fill=(0, 112, 240, 255))
        draw.text((512, 512), "TFP", fill="white", anchor="mm")
        for s in sizes:
            resized = img.resize((s, s), Image.LANCZOS)
            resized.save(iconset / f"icon_{s}x{s}.png")
            if s <= 256:
                dbl = img.resize((s * 2, s * 2), Image.LANCZOS)
                dbl.save(iconset / f"icon_{s}x{s}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset)], check=True)
        shutil.rmtree(iconset)
    except Exception as exc:
        warn(f"could not generate .icns: {exc}; macOS bundle will have default icon")


def _write_info_plist() -> None:
    if not ICON_PATH.exists():
        _create_icns()
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>TaxFlowPro</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>{APP_IDENTIFIER}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>{VERSION}</string>
    <key>CFBundleVersion</key>
    <string>{VERSION}</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSBackgroundOnly</key>
    <false/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>
'''
    INFO_PLIST.write_text(content, encoding="utf-8")


def _write_spec() -> Path:
    if not ICON_PATH.exists():
        _create_icns()
    spec_path = resource_path("macos", "TaxFlowPro_macos.spec")
    content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE
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
            added_files.append((str(sub), f"vendored/{sub.name}"))

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
    name="TaxFlowPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(Path(r"{ICON_PATH}")) if Path(r"{ICON_PATH}").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TaxFlowPro",
)

app = BUNDLE(
    coll,
    name="{BUNDLE_NAME}",
    icon=str(Path(r"{ICON_PATH}")) if Path(r"{ICON_PATH}").exists() else None,
    bundle_identifier="{APP_IDENTIFIER}",
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
    # Post-process Info.plist with our own values.
    bundle_plist = BUNDLE_DIR / "Contents" / "Info.plist"
    if bundle_plist.exists():
        _write_info_plist()
        shutil.copy2(INFO_PLIST, bundle_plist)
    # Sign if identity provided.
    identity = os.environ.get("CODE_SIGN_IDENTITY")
    if identity:
        subprocess.run(["codesign", "--deep", "--force", "--verify", "--sign", identity, str(BUNDLE_DIR)], check=False)
    else:
        warn("no CODE_SIGN_IDENTITY set; macOS bundle will be unsigned")


def _build_dmg() -> None:
    create_dmg = shutil.which("create-dmg")
    if not create_dmg:
        warn("create-dmg not found; DMG not produced. App bundle is ready.")
        return
    output = INSTALLER_DIR / INSTALLER_NAME
    if output.exists():
        output.unlink()
    cmd = [
        create_dmg,
        "--volname", f"{APP_NAME} {VERSION}",
        "--window-pos", "200", "120",
        "--window-size", "600", "400",
        "--icon-size", "100",
        "--app-drop-link", "450", "185",
        str(output),
        str(BUNDLE_DIR),
    ]
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TaxFlow Pro macOS bundle")
    parser.add_argument("--skip-pyinstaller", action="store_true")
    args = parser.parse_args()

    if not args.skip_pyinstaller:
        _run_pyinstaller()
    else:
        if not BUNDLE_DIR.exists():
            fail(f"--skip-pyinstaller requested but {BUNDLE_DIR} does not exist")

    _build_dmg()
    print(f"[macos] app bundle: {BUNDLE_DIR}")
    if (INSTALLER_DIR / INSTALLER_NAME).exists():
        print(f"[macos] DMG: {INSTALLER_DIR / INSTALLER_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
