"""TaxFlow Pro v3.10 — vendored binary build helper.

Builds the ``vendored/`` tree for Tesseract OCR and Poppler pdftools. The
launcher reads these paths via ``TESSERACT_CMD`` and ``POPPLER_PATH``.

This script may download upstream Windows binaries at build time. It never
makes network calls at runtime.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants and directory layout
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDORED_DIR = PROJECT_ROOT / "vendored"
TESSERACT_DIR = VENDORED_DIR / "tesseract"
POPPLER_DIR = VENDORED_DIR / "poppler"

# Well-known upstream Windows distribution URLs. These are community-maintained
# portable archives; replace with pinned internal mirrors in production builds.
WINDOWS_TESSERACT_URL = (
    "https://github.com/UB-Mannheim/tesseract/wiki"
)
WINDOWS_POPPLER_URL = (
    "https://github.com/oschwartz10612/poppler-windows/releases/"
)

# Ubuntu packages that satisfy the same binaries on Debian-based Linux.
LINUX_PACKAGES = ["tesseract-ocr", "poppler-utils"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Optional[Path] = None, check: bool = True) -> None:
    """Run a subprocess with friendly error output."""
    print("[build_vendored] running:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=check)


def _download(url: str, dest: Path) -> None:
    """Download a file using curl or urllib as fallback."""
    if shutil.which("curl"):
        _run(["curl", "-fsSL", "-o", str(dest), url])
        return
    if shutil.which("wget"):
        _run(["wget", "-q", "-O", str(dest), url])
        return

    import urllib.request
    print("[build_vendored] downloading via urllib:", url)
    urllib.request.urlretrieve(url, str(dest))


def _extract_zip(archive: Path, dest: Path) -> None:
    """Extract a zip archive into a destination directory."""
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest)


def _prompt_manual_download(name: str, urls: list[str]) -> None:
    """Print instructions when an automatic download is not implemented."""
    print(f"\n[build_vendored] automatic {name} download is not available on this platform.")
    print("Please download the portable archive manually from one of these locations:")
    for url in urls:
        print(f"  - {url}")
    print(f"Then extract it so the binaries land under:")
    print(f"  - Tesseract: {TESSERACT_DIR}")
    print(f"  - Poppler:   {POPPLER_DIR / 'bin' if platform.system() == 'Windows' else POPPLER_DIR}")


# ---------------------------------------------------------------------------
# Tesseract builders
# ---------------------------------------------------------------------------


def build_tesseract_windows() -> None:
    """Locate or download the UB Mannheim portable Tesseract build for Windows.

    Because the exact GitHub release URL changes per version and is not a
    stable permalink, this helper attempts common patterns and falls back to
    printing manual download instructions if they fail.
    """
    print("[build_vendored] locating/downloading Windows Tesseract...")
    tessdata_dir = TESSERACT_DIR / "tessdata"
    tessdata_dir.mkdir(parents=True, exist_ok=True)

    # If a system Tesseract is available, mirror its binaries and tessdata.
    system_tess = shutil.which("tesseract")
    if system_tess:
        system_root = Path(system_tess).parent
        dest_root = TESSERACT_DIR
        for fname in ("tesseract.exe", "tesseract"):
            src = system_root / fname
            if src.exists():
                shutil.copy2(src, dest_root / fname)
        if (system_root / "tessdata").exists():
            for src in (system_root / "tessdata").iterdir():
                shutil.copy2(src, tessdata_dir / src.name)
        print(f"[build_vendored] mirrored system Tesseract from {system_root}")
        return

    _prompt_manual_download(
        "Tesseract",
        [
            "https://github.com/UB-Mannheim/tesseract/wiki",
            "https://digi.bib.uni-mannheim.de/tesseract/",
        ],
    )
    print("\nExpected layout after extraction:")
    print(f"  {TESSERACT_DIR / 'tesseract.exe'}")
    print(f"  {TESSERACT_DIR / 'tessdata' / 'eng.traineddata'}")


def build_tesseract_macos() -> None:
    """Provide macOS Tesseract vendoring instructions."""
    print("[build_vendored] macOS Tesseract vendoring notes:")
    print("  Install Homebrew dependencies:")
    print("    brew install tesseract")
    print("  Then copy binaries and tessdata into the vendored tree:")
    print(f"    cp $(brew --prefix tesseract)/bin/tesseract {TESSERACT_DIR}/")
    print(f"    cp -r $(brew --prefix tesseract)/share/tessdata {TESSERACT_DIR}/")


def build_tesseract_linux() -> None:
    """Provide Linux Tesseract vendoring instructions."""
    print("[build_vendored] Linux Tesseract vendoring notes:")
    print("  Use the system package manager:")
    print("    sudo apt-get install tesseract-ocr")
    print("  Or mirror the system binary into the vendored tree:")
    print(f"    cp $(which tesseract) {TESSERACT_DIR}/")
    print(f"    cp -r /usr/share/tesseract-ocr/4.00/tessdata {TESSERACT_DIR}/")


# ---------------------------------------------------------------------------
# Poppler builders
# ---------------------------------------------------------------------------


def build_poppler_windows() -> None:
    """Locate or download Windows Poppler binaries.

    Tries the system PATH first; otherwise prints download instructions.
    """
    print("[build_vendored] locating/downloading Windows Poppler...")
    poppler_bin = POPPLER_DIR / "bin"
    poppler_bin.mkdir(parents=True, exist_ok=True)

    # Mirror system Poppler if available.
    for binary in ("pdftotext.exe", "pdfimages.exe", "pdfinfo.exe", "pdftoppm.exe"):
        src = shutil.which(binary)
        if src:
            shutil.copy2(src, poppler_bin / binary)
    if any((poppler_bin / b).exists() for b in ("pdftotext.exe", "pdfimages.exe")):
        print(f"[build_vendored] mirrored system Poppler binaries into {poppler_bin}")
        return

    _prompt_manual_download(
        "Poppler",
        [
            "https://github.com/oschwartz10612/poppler-windows/releases",
            "https://blog.alivate.com.au/poppler-windows/",
        ],
    )
    print("\nExpected layout after extraction:")
    print(f"  {poppler_bin / 'pdftotext.exe'}")
    print(f"  {poppler_bin / 'pdfimages.exe'}")
    print(f"  {poppler_bin / 'pdfinfo.exe'}")
    print(f"  {poppler_bin / 'pdftoppm.exe'}")


def build_poppler_macos() -> None:
    """Provide macOS Poppler vendoring instructions."""
    print("[build_vendored] macOS Poppler vendoring notes:")
    print("  Install Homebrew dependencies:")
    print("    brew install poppler")
    print("  Then copy binaries into the vendored tree:")
    print(f"    cp $(brew --prefix poppler)/bin/pdftotext {POPPLER_DIR}/")
    print(f"    cp $(brew --prefix poppler)/bin/pdfimages {POPPLER_DIR}/")
    print(f"    cp $(brew --prefix poppler)/bin/pdfinfo {POPPLER_DIR}/")


def build_poppler_linux() -> None:
    """Provide Linux Poppler vendoring instructions."""
    print("[build_vendored] Linux Poppler vendoring notes:")
    print("  Use the system package manager:")
    print("    sudo apt-get install poppler-utils")
    print("  Or mirror the system binaries into the vendored tree:")
    for binary in ("pdftotext", "pdfimages", "pdfinfo", "pdftoppm"):
        print(f"    cp $(which {binary}) {POPPLER_DIR}/")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_all() -> int:
    """Populate the vendored binary tree for the current platform."""
    system = platform.system()
    VENDORED_DIR.mkdir(parents=True, exist_ok=True)

    if system == "Windows":
        build_tesseract_windows()
        build_poppler_windows()
    elif system == "Darwin":
        build_tesseract_macos()
        build_poppler_macos()
    else:
        build_tesseract_linux()
        build_poppler_linux()

    print("\n[build_vendored] vendored tree layout:")
    for root, dirs, files in os.walk(VENDORED_DIR):
        level = root.replace(str(VENDORED_DIR), "").count(os.sep)
        indent = " " * 2 * level
        print(f"{indent}{Path(root).name}/")
        subindent = " " * 2 * (level + 1)
        for file in sorted(files)[:20]:  # cap listing
            print(f"{subindent}{file}")

    return 0


def main() -> int:
    return build_all()


if __name__ == "__main__":
    sys.exit(main())
