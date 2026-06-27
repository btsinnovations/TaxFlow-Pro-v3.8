"""Windows installer build for TaxFlow Pro.

Produces:
- dist/pyinstaller/TaxFlowPro/          (onedir bundle)
- dist/installers/TaxFlowPro-3.10.0-Setup.exe

The installer is created via NSIS if makensis is available, otherwise via
Inno Setup if iscc is available, otherwise the build stops at the PyInstaller
bundle with instructions.
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
    VERSION,
    PROJECT_ROOT,
    FRONTEND_DIR,
    ALEMBIC_DIR,
    REQUIREMENTS_FILE,
    VENDORED_DIR,
    LAUNCHER_SCRIPT,
    DIST_ROOT,
    INSTALLER_DIR,
    PYINSTALLER_DIR,
    resource_path,
    fail,
    warn,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SPEC_PATH = resource_path("windows", "TaxFlowPro.spec")
NSIS_SCRIPT = resource_path("windows", "installer.nsi")
INNO_SCRIPT = resource_path("windows", "installer.iss")
ICON_PATH = resource_path("assets", "icon.ico")

BUNDLE_NAME = "TaxFlowPro"
BUNDLE_DIR = PYINSTALLER_DIR / BUNDLE_NAME

INSTALLER_NAME = f"TaxFlowPro-{VERSION}-Setup.exe"


def _pyinstaller_available() -> bool:
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _write_pyinstaller_spec() -> None:
    # Ensure a basic .ico exists.
    if not ICON_PATH.exists():
        _create_default_icon()

    # We use a .spec file so we can include frontend/dist and alembic as data.
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
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
    added_files.extend(
        (str(d), "vendored/" + d.name) for d in vendored.iterdir() if d.is_dir()
    )

ml = root / "ml"
if ml.exists():
    added_files.append((str(ml), "ml"))

a = Analysis(
    [str(root / "scripts" / "taxflow_launcher.py")],
    pathex=[str(root), str(root / "scripts"), str(root / "scripts" / "packaging")],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.workers",
        "fastapi",
        "fastapi.staticfiles",
        "starlette.staticfiles",
        "starlette.responses",
        "sqlalchemy",
        "alembic",
        "alembic.command",
        "alembic.config",
        "alembic.runtime.migration",
        "alembic.script",
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
        "sklearn.utils._typedefs",
        "sklearn.neighbors._partition_nodes",
        "sklearn.linear_model._logistic",
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
        "passlib",
        "passlib.handlers.bcrypt",
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
    console=False,
    icon=str(Path(r"{ICON_PATH}")),
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
    SPEC_PATH.write_text(spec_content, encoding="utf-8")


def _create_default_icon() -> None:
    """Create a trivial ICO file so PyInstaller has an icon."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([16, 16, 240, 240], radius=32, fill=(0, 112, 240, 255))
        draw.text((128, 128), "TFP", fill="white", anchor="mm")
        sizes = [16, 32, 48, 64, 128, 256]
        frames = [img.resize((s, s), Image.LANCZOS) for s in sizes]
        frames[0].save(ICON_PATH, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
    except Exception as exc:
        warn(f"could not generate icon: {exc}; installer will use PyInstaller default")


def _run_pyinstaller() -> None:
    if not _pyinstaller_available():
        fail("PyInstaller not available; install with `pip install pyinstaller`")
    _write_pyinstaller_spec()
    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC_PATH),
    ]
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    # PyInstaller 6+ places onedir bundles directly under dist/<name>.
    expected = DIST_ROOT / BUNDLE_NAME
    if expected.exists() and expected != BUNDLE_DIR:
        if BUNDLE_DIR.exists():
            shutil.rmtree(BUNDLE_DIR)
        shutil.move(str(expected), str(BUNDLE_DIR))


def _write_nsis_script() -> None:
    content = f'''; NSIS installer script for {APP_NAME} {VERSION}
!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "{APP_NAME}"
OutFile "{INSTALLER_DIR / INSTALLER_NAME}"
InstallDir "$LOCALAPPDATA\\{BUNDLE_NAME}"
RequestExecutionLevel user

!define MUI_ICON "{ICON_PATH}"
!define MUI_UNICON "{ICON_PATH}"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "{BUNDLE_DIR}\\*.*"

    ; Create user data directories outside install dir
    CreateDirectory "$LOCALAPPDATA\\{BUNDLE_NAME}\\db"
    CreateDirectory "$LOCALAPPDATA\\{BUNDLE_NAME}\\backups"
    CreateDirectory "$LOCALAPPDATA\\{BUNDLE_NAME}\\uploads"
    CreateDirectory "$LOCALAPPDATA\\{BUNDLE_NAME}\\ml"
    CreateDirectory "$LOCALAPPDATA\\{BUNDLE_NAME}\\logs"

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\\{APP_NAME}"
    CreateShortcut "$SMPROGRAMS\\{APP_NAME}\\{APP_NAME}.lnk" "$INSTDIR\\{BUNDLE_NAME}.exe"
    CreateShortcut "$SMPROGRAMS\\{APP_NAME}\\Uninstall {APP_NAME}.lnk" "$INSTDIR\\uninst.exe"

    ; Uninstaller
    WriteUninstaller "$INSTDIR\\uninst.exe"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{BUNDLE_NAME}" "DisplayName" "{APP_NAME}"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{BUNDLE_NAME}" "UninstallString" "$\\\"$INSTDIR\\uninst.exe$\\\""
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{BUNDLE_NAME}" "DisplayVersion" "{VERSION}"
    WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{BUNDLE_NAME}" "InstallLocation" "$INSTDIR"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\*.*"
    RMDir /r "$INSTDIR"
    Delete "$SMPROGRAMS\\{APP_NAME}\\*.lnk"
    RMDir "$SMPROGRAMS\\{APP_NAME}"
    DeleteRegKey HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{BUNDLE_NAME}"
SectionEnd

Function .onInit
    ; Silent install support
    IfSilent 0 +2
    SetSilent silent
FunctionEnd
'''
    NSIS_SCRIPT.write_text(content, encoding="utf-8")


def _write_inno_script() -> None:
    app_id = APP_NAME.replace(" ", "") + "_IS1"
    content = f'''; Inno Setup script for {APP_NAME} {VERSION}
#define AppName "{APP_NAME}"
#define AppVersion "{VERSION}"
#define AppExeName "{BUNDLE_NAME}.exe"
#define AppId "{app_id}"

[Setup]
AppName={{{{#AppName}}}}
AppVersion={{{{#AppVersion}}}}
DefaultDirName={{{{autopf}}}}\\{BUNDLE_NAME}
DefaultGroupName={{{{#AppName}}}}
OutputDir={INSTALLER_DIR}
OutputBaseFilename=TaxFlowPro-{VERSION}-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile={ICON_PATH}
UninstallDisplayIcon={{{{app}}}}\\{{{{#AppExeName}}}}

[Files]
Source: "{BUNDLE_DIR}\\*"; DestDir: "{{{{app}}}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{{{group}}}}\\{{{{#AppName}}}}"; Filename: "{{{{app}}}}\\{{{{#AppExeName}}}}"
Name: "{{{{group}}}}\\Uninstall {{{{#AppName}}}}"; Filename: "{{{{uninstallexe}}}}"

[Run]
Filename: "{{{{app}}}}\\{{{{#AppExeName}}}}"; Description: "Launch {{{{#AppName}}}}"; Flags: postinstall skipifsilent nowait

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{BUNDLE_NAME}"; ValueType: string; ValueName: "DisplayName"; ValueData: "{{{{#AppName}}}}"; Flags: uninsdeletekey
'''
    INNO_SCRIPT.write_text(content, encoding="utf-8")


def _build_zip_installer() -> None:
    """Create a self-contained zip installer for systems without NSIS/Inno."""
    zip_path = INSTALLER_DIR / f"TaxFlowPro-{VERSION}-Setup.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    base = str(zip_path.with_suffix(""))
    shutil.make_archive(base, "zip", root_dir=BUNDLE_DIR)
    print(f"[windows] zip installer produced: {zip_path}")


NSIS_DEFAULT_DIR = Path(os.environ.get("NSIS_DIR", r"C:\Program Files (x86)\NSIS"))


def _find_nsis() -> str | None:
    """Return path to makensis.exe, checking PATH and the default NSIS dir."""
    path_exe = shutil.which("makensis")
    if path_exe:
        return path_exe
    candidate = NSIS_DEFAULT_DIR / "makensis.exe"
    if candidate.exists():
        return str(candidate)
    return None


def _find_inno() -> str | None:
    """Return path to iscc.exe, checking PATH and common install locations."""
    path_exe = shutil.which("iscc")
    if path_exe:
        return path_exe
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\iscc.exe"),
        Path(r"C:\Program Files\Inno Setup 6\iscc.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\iscc.exe"),
        Path(r"C:\Program Files\Inno Setup 5\iscc.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _build_installer() -> bool:
    """Try NSIS, then Inno Setup, then fall back to a portable zip. Return True if any wrapper produced."""
    nsis = _find_nsis()
    if nsis:
        _write_nsis_script()
        cmd = [nsis, "/V2", str(NSIS_SCRIPT)]
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        return True

    iscc = _find_inno()
    if iscc:
        _write_inno_script()
        cmd = [iscc, str(INNO_SCRIPT)]
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        return True

    warn("neither makensis nor iscc found; falling back to portable zip installer")
    _build_zip_installer()
    warn(f"PyInstaller bundle is ready at: {BUNDLE_DIR}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build TaxFlow Pro Windows installer")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Assume PyInstaller bundle already exists")
    args = parser.parse_args()

    if platform.system() != "Windows":
        warn("not on Windows; this script can only produce the PyInstaller bundle natively")

    if not args.skip_pyinstaller:
        _run_pyinstaller()
    else:
        if not BUNDLE_DIR.exists():
            fail(f"--skip-pyinstaller requested but {BUNDLE_DIR} does not exist")

    produced = _build_installer()
    if produced:
        print(f"[windows] installer produced: {INSTALLER_DIR / INSTALLER_NAME}")
    else:
        print(f"[windows] bundle produced (no installer wrapper): {BUNDLE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
