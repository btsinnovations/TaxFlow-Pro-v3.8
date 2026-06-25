"""Download and stage vendored Tesseract + Poppler binaries.

This is a build-time helper. It fetches portable Windows releases and stages
them under ``vendored/tesseract`` and ``vendored/poppler`` so the packaged
app does not require system installs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendored"
TESSERACT_DIR = VENDOR_ROOT / "tesseract"
POPPLER_DIR = VENDOR_ROOT / "poppler"

# Known portable release URLs. Update these as newer releases become available.
# Poppler Windows build (oschwartz10612 repackages conda-forge builds).
# The official Tesseract Windows release is an NSIS installer (exe), not a zip.
# The vendoring helper downloads the installer and runs it silently into a temp
# directory, then copies the portable files (tesseract.exe + DLLs + tessdata)
# into the vendored tree. A true portable zip is not published by upstream.
TESSERACT_URL = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
POPPLER_URL = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip"


def _copytree_replace(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _run_silent_nsis(installer: Path, target_dir: Path) -> bool:
    """Run the NSIS installer silently into target_dir.

    NSIS requires /D to be the LAST argument and the path must NOT be quoted,
    even if it contains spaces.

    The installer needs elevation on some Windows configurations; use the
    Windows ``runas`` verb so the UAC prompt is surfaced if needed.
    """
    cmd = [str(installer), "/S", f"/D={target_dir}"]
    print("Running silent installer:", " ".join(cmd))
    # NSIS installers that require elevation may fail with WinError 740. The
    # exception happens during subprocess.run, so we catch it directly.
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        if "740" in str(exc) or "elevation" in str(exc):
            print("Installer requested elevation; retrying with runas verb...")
            try:
                import ctypes
                # SEE_MASK_NO_CONSOLE = 0x00008000, SW_SHOWNORMAL = 1
                ctypes.windll.shell32.ShellExecuteW(None, "runas", str(installer), f"/S /D={target_dir}", None, 1)
                deadline = time.monotonic() + 120.0
                while time.monotonic() < deadline:
                    if (target_dir / "tesseract.exe").exists():
                        return True
                    time.sleep(0.5)
                return False
            except Exception as inner:
                print("ERROR running elevated installer:", inner)
                return False
        raise
    if proc.returncode != 0:
        print("Installer stdout:", proc.stdout)
        print("Installer stderr:", proc.stderr)
    return proc.returncode == 0


def vendor_tesseract() -> bool:
    print("Downloading Tesseract from", TESSERACT_URL)
    try:
        with tempfile.TemporaryDirectory() as td:
            installer = Path(td) / "tesseract-setup.exe"
            urllib.request.urlretrieve(TESSERACT_URL, installer)
            install_dir = Path(td) / "tesseract-install"
            if not _run_silent_nsis(installer, install_dir):
                print("ERROR: Tesseract installer failed")
                return False
            # The installer writes files directly under install_dir.
            tess_exe = install_dir / "tesseract.exe"
            tessdata_dir = install_dir / "tessdata"
            if not tess_exe.exists():
                print("ERROR: tesseract.exe not found after silent install")
                return False
            if not tessdata_dir.exists():
                print("ERROR: tessdata directory not found after silent install")
                return False
            # Stage the minimum portable set into the vendored tree.
            if TESSERACT_DIR.exists():
                shutil.rmtree(TESSERACT_DIR)
            TESSERACT_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(tess_exe, TESSERACT_DIR / "tesseract.exe")
            for dll in install_dir.glob("*.dll"):
                shutil.copy(dll, TESSERACT_DIR / dll.name)
            shutil.copytree(tessdata_dir, TESSERACT_DIR / "tessdata")
        print("Tesseract vendored to", TESSERACT_DIR)
        return True
    except Exception as exc:
        print("ERROR vendoring Tesseract:", exc)
        return False


def vendor_poppler() -> bool:
    print("Downloading Poppler from", POPPLER_URL)
    try:
        with tempfile.TemporaryDirectory() as td:
            z = Path(td) / "pop.zip"
            urllib.request.urlretrieve(POPPLER_URL, z)
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(td)
            extracted = Path(td)
            candidates = list(extracted.rglob("pdftotext.exe"))
            if not candidates:
                print("ERROR: pdftotext.exe not found in downloaded archive")
                return False
            src = candidates[0].parent
            _copytree_replace(src, POPPLER_DIR)
        print("Poppler vendored to", POPPLER_DIR)
        return True
    except Exception as exc:
        print("ERROR vendoring Poppler:", exc)
        return False


def main() -> int:
    VENDOR_ROOT.mkdir(parents=True, exist_ok=True)
    ok1 = vendor_tesseract()
    ok2 = vendor_poppler()
    if ok1 and ok2:
        print("OK: vendored binaries staged.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
