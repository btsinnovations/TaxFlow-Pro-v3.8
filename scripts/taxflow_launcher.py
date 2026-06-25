"""TaxFlow Pro v3.10 — local-first application launcher.

This is the canonical launcher used by source installs, PyInstaller bundles,
and future packaging. It:

  1. Resolves the OS-specific ``TAXFLOW_LOCAL_ROOT`` (outside the install dir).
  2. Ensures required subdirectories exist (db, backups, uploads, ml, logs).
  3. Wires vendored Tesseract + Poppler binaries.
  4. Runs Alembic migrations against the local database.
  5. Starts Uvicorn serving ``backend.api:app`` on 127.0.0.1:8000.
  6. Opens the user's default browser to the local web UI.
  7. Blocks until the server exits.

The launcher works both when running from the project source tree and inside a
PyInstaller one-dir bundle (``sys.frozen`` / ``sys._MEIPASS``).
"""
from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


# ---------------------------------------------------------------------------
# Project / bundle root resolution
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Return the directory that contains the TaxFlow backend code.

    In a PyInstaller bundle the extracted assets live at ``sys._MEIPASS``.
    In source mode the project root is two directories above this script
    (``scripts/taxflow_launcher.py`` -> project root).
    """
    if getattr(sys, "frozen", False):
        # _MEIPASS points at the extracted bundle root.
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def _is_frozen_onedir() -> bool:
    """Return True when running inside a PyInstaller one-directory bundle."""
    frozen = getattr(sys, "frozen", False)
    if not frozen:
        return False
    # PyInstaller one-dir sets sys.frozen to "application_bundle" on macOS
    # or True on Windows/Linux and the executable lives in the bundle root
    # (as opposed to one-file where executable is a temporary extractor).
    exe = Path(sys.executable).resolve()
    meipass = Path(sys._MEIPASS).resolve()
    # In onedir the executable is inside the bundle root; in onefile it is the
    # parent directory of the temporary _MEI folder.
    return exe.parent == meipass or exe == meipass


def _wait_for_health(url: str, timeout: float = 30.0) -> bool:
    """Poll /health until the server responds or the deadline expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{url}/health", timeout=1.0) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Local data directory resolution
# ---------------------------------------------------------------------------


def _local_root() -> Path:
    """Return the platform-specific user-writable local data directory.

    Order of precedence:
      1. ``TAXFLOW_LOCAL_ROOT`` environment variable (absolute path).
      2. OS-specific default:
         - Windows: ``%LOCALAPPDATA%\\TaxFlowPro``
         - macOS: ``~/Library/Application Support/TaxFlowPro``
         - Linux: ``~/.local/share/TaxFlowPro`` (or ``$XDG_DATA_HOME/TaxFlowPro``)
    """
    env_root = os.environ.get("TAXFLOW_LOCAL_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()

    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = Path.home() / "AppData" / "Local"
        return Path(base) / "TaxFlowPro"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "TaxFlowPro"

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "TaxFlowPro"
    return Path.home() / ".local" / "share" / "TaxFlowPro"


def _ensure_dirs(local_root: Path) -> None:
    """Create the canonical local subdirectories."""
    for sub in ("db", "backups", "uploads", "ml", "logs"):
        (local_root / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Vendored binary configuration (Tesseract + Poppler)
# ---------------------------------------------------------------------------


def _configure_vendored_binaries() -> dict[str, str | None]:
    """Point pytesseract and pdf2image at the vendored binaries.

    Sets environment variables that downstream code also reads:
      - ``TESSERACT_CMD`` -> vendored ``tesseract`` executable
      - ``TESSDATA_PREFIX`` -> vendored ``tessdata`` directory
      - ``POPPLER_PATH`` -> vendored ``poppler`` directory
      - ``PATH`` is extended to include the Poppler bin directory so that
        pdf2image's auto-discovery works.

    Also mutates the imported ``pytesseract.pytesseract`` module attribute at
    runtime so that later parser imports use the vendored executable.
    """
    root = _project_root()
    vendored = root / "vendored"
    system = platform.system()
    ext = ".exe" if system == "Windows" else ""

    configured: dict[str, str | None] = {
        "TESSERACT_CMD": None,
        "TESSDATA_PREFIX": None,
        "POPPLER_PATH": None,
    }

    tess_dir = vendored / "tesseract"
    tess_exe = tess_dir / f"tesseract{ext}"
    if tess_exe.exists():
        os.environ["TESSERACT_CMD"] = str(tess_exe)
        configured["TESSERACT_CMD"] = str(tess_exe)

    tessdata_dir = tess_dir / "tessdata"
    if tessdata_dir.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        configured["TESSDATA_PREFIX"] = str(tessdata_dir)

    poppler_dir = vendored / "poppler"
    poppler_bin = poppler_dir / ("bin" if system == "Windows" else "")
    if not poppler_bin.exists():
        poppler_bin = poppler_dir
    pdftotext_exe = poppler_bin / f"pdftotext{ext}"

    # On Unix, fall back to system binaries if vendored ones are absent.
    if system != "Windows" and not tess_exe.exists():
        sys_tess = shutil.which("tesseract")
        if sys_tess:
            tess_exe = Path(sys_tess)
    if system != "Windows" and not pdftotext_exe.exists():
        sys_pdftotext = shutil.which("pdftotext")
        if sys_pdftotext:
            poppler_bin = Path(sys_pdftotext).parent
            pdftotext_exe = poppler_bin / "pdftotext"

    if tess_exe.exists():
        os.environ["TESSERACT_CMD"] = str(tess_exe)
        configured["TESSERACT_CMD"] = str(tess_exe)

    tessdata_dir = tess_dir / "tessdata"
    if tessdata_dir.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        configured["TESSDATA_PREFIX"] = str(tessdata_dir)
    elif system != "Windows":
        # System install usually ships default eng.traineddata.
        sys_tessdata = "/usr/share/tesseract-ocr/4.00/tessdata"
        if Path(sys_tessdata).exists():
            os.environ["TESSDATA_PREFIX"] = sys_tessdata
            configured["TESSDATA_PREFIX"] = sys_tessdata

    if pdftotext_exe.exists():
        poppler_path = str(poppler_bin)
        os.environ["POPPLER_PATH"] = poppler_path
        configured["POPPLER_PATH"] = poppler_path
        os.environ["PATH"] = poppler_path + os.pathsep + os.environ.get("PATH", "")

    # Eagerly import pytesseract and pdf2image here, before the backend is
    # imported, so we can seed the module-level binary paths. The parser code
    # imports these later and inherits the configured values.
    try:
        import pytesseract
        import pytesseract.pytesseract as _tess_module

        if configured["TESSERACT_CMD"]:
            _tess_module.tesseract_cmd = configured["TESSERACT_CMD"]
    except Exception:
        pass

    try:
        import pdf2image
        # pdf2image reads the poppler_path argument at call time; env var is not
        # enough. We patch the module-level default helper if available.
        pdf2image.convert_from_path  # force import of the submodule
        poppler_path = configured.get("POPPLER_PATH")
        if poppler_path and hasattr(pdf2image, "poppler_path"):
            pdf2image.poppler_path = poppler_path  # type: ignore[attr-defined]
    except Exception:
        pass

    return configured


# ---------------------------------------------------------------------------
# Uvicorn / server helpers
# ---------------------------------------------------------------------------


def _find_uvicorn() -> str | None:
    """Return a vendored/venv uvicorn executable path, or None to use ``python -m``."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        exe = exe_dir / ("uvicorn.exe" if platform.system() == "Windows" else "uvicorn")
        if exe.exists():
            return str(exe)

    root = _project_root()
    site_candidates = [
        root / ".venv" / "Lib" / "site-packages",
        root / "venv" / "Lib" / "site-packages",
        root / "backend" / ".venv" / "Lib" / "site-packages",
    ]
    for site in site_candidates:
        if site.exists():
            scripts_dir = site.parent.parent / "Scripts" if platform.system() == "Windows" else site.parent.parent / "bin"
            uvicorn_exe = scripts_dir / ("uvicorn.exe" if platform.system() == "Windows" else "uvicorn")
            if uvicorn_exe.exists():
                return str(uvicorn_exe)

    return None


def _build_uvicorn_command(host: str, port: int) -> list[str]:
    """Build the command that starts Uvicorn."""
    uvicorn_exe = _find_uvicorn()
    if uvicorn_exe:
        return [uvicorn_exe, "backend.api:app", "--host", host, "--port", str(port)]
    return [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", host, "--port", str(port)]


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------


def _run_migrations(local_root: Path) -> int:
    """Run Alembic migrations against the configured local database."""
    root = _project_root()
    alembic_ini = root / "alembic.ini"
    db_url = f"sqlite:///{local_root / 'db' / 'taxflow.db'}"

    os.environ.setdefault("DATABASE_URL", db_url)
    os.environ.setdefault("ALEMBIC_CONFIG", str(alembic_ini.resolve()))
    os.environ.setdefault("TAXFLOW_LOCAL_ROOT", str(local_root))

    try:
        from alembic.config import Config
        from alembic import command

        # Alembic resolves ``script_location = alembic`` relative to the
        # current working directory. Ensure we run from the project root so
        # the migrations folder is found regardless of how the launcher was
        # invoked (source tree ``scripts/`` vs PyInstaller bundle).
        original_cwd = os.getcwd()
        os.chdir(str(root))
        try:
            cfg = Config(str(alembic_ini))
            cfg.set_main_option("sqlalchemy.url", db_url)
            command.upgrade(cfg, "head")
            print("[launcher] migrations complete")
        finally:
            os.chdir(original_cwd)
        return 0
    except Exception as exc:
        print(f"[launcher] migration failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


# ---------------------------------------------------------------------------
# Browser launch
# ---------------------------------------------------------------------------


def _open_browser(url: str, delay_seconds: float = 1.5) -> None:
    """Open the default browser after a short delay so the server is ready."""
    if os.environ.get("TAXFLOW_NO_BROWSER", "").lower() in ("1", "true", "yes"):
        return
    def _open() -> None:
        try:
            time.sleep(delay_seconds)
            webbrowser.open(url, new=2)
        except Exception as exc:
            print(f"[launcher] could not open browser: {exc}", file=sys.stderr)

    threading.Thread(target=_open, daemon=True).start()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Launch the TaxFlow Pro local application."""
    local_root = _local_root()
    _ensure_dirs(local_root)

    configured = _configure_vendored_binaries()

    # Ensure the project root is on sys.path so ``backend.api:app`` resolves.
    project_root = _project_root()
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # Finalize environment for the backend.
    db_url = f"sqlite:///{local_root / 'db' / 'taxflow.db'}"
    os.environ["DATABASE_URL"] = db_url
    os.environ["TAXFLOW_LOCAL_ROOT"] = str(local_root)
    os.environ.setdefault("TAXFLOW_ENVIRONMENT", "production")
    os.environ.setdefault("TAXFLOW_RUNTIME_MODE", "offline")
    os.environ.setdefault("TAXFLOW_SINGLE_USER", "true")

    host = os.environ.get("TAXFLOW_HOST", "127.0.0.1")
    port = int(os.environ.get("TAXFLOW_PORT", "8000"))
    url = f"http://{host}:{port}"

    print(f"[launcher] project root: {project_root}")
    print(f"[launcher] local root:   {local_root}")
    print(f"[launcher] database:    {db_url}")
    if configured.get("TESSERACT_CMD"):
        print(f"[launcher] tesseract:   {configured['TESSERACT_CMD']}")
    if configured.get("POPPLER_PATH"):
        print(f"[launcher] poppler:     {configured['POPPLER_PATH']}")

    if _run_migrations(local_root) != 0:
        return 1

    if _is_frozen_onedir():
        # When bundled as a PyInstaller one-dir app we are the interpreter:
        # run uvicorn in-process so we do not need to discover an external
        # uvicorn executable and so the bundled sys.path is preserved.
        _open_browser(url)
        print(f"[launcher] starting uvicorn in-process on {url}")
        import uvicorn
        uvicorn.run(
            "backend.api:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,
        )
        return 0

    cmd = _build_uvicorn_command(host, port)
    print(f"[launcher] starting server: {' '.join(cmd)}")

    proc = subprocess.Popen(cmd, cwd=str(project_root))
    try:
        if _wait_for_health(url):
            _open_browser(url, delay_seconds=0.5)
        else:
            print(f"[launcher] warning: server did not report healthy at {url}/health", file=sys.stderr)
        proc.wait()
    except KeyboardInterrupt:
        print("\n[launcher] received interrupt; stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
