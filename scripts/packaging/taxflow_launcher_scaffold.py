"""Scaffold launcher script for Bundles B+C.

This file is intended to be copied to scripts/taxflow_launcher.py when the
real launcher is missing. It implements the required behavior so that packaging
can be tested end-to-end while Bundles B+C finish their work.

When the real launcher exists, this file is ignored.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path


def _project_root() -> Path:
    """Return the project root whether running from source or a frozen bundle."""
    if getattr(sys, "frozen", False):
        # In onedir mode the executable lives in the bundle root; data files
        # (frontend/dist, alembic, vendored, etc.) are next to it.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _local_root() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "TaxFlowPro"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "TaxFlowPro"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "TaxFlowPro"
    return Path.home() / ".local" / "share" / "TaxFlowPro"


def _ensure_dirs(local_root: Path) -> None:
    for sub in ("db", "backups", "uploads", "ml", "logs"):
        (local_root / sub).mkdir(parents=True, exist_ok=True)


def _set_vendor_paths() -> None:
    root = _project_root()
    vendored = root / "vendored"
    tess = vendored / "tesseract"
    pop = vendored / "poppler"
    ext = ".exe" if platform.system() == "Windows" else ""

    if (tess / f"tesseract{ext}").exists():
        os.environ.setdefault("TESSERACT_CMD", str(tess / f"tesseract{ext}"))
        os.environ.setdefault("TESSDATA_PREFIX", str(tess / "tessdata"))
    if (pop / f"pdftotext{ext}").exists():
        os.environ.setdefault("POPPLER_PATH", str(pop))

    # Also add vendored dirs to PATH so bootstrap/shutil.which can find them.
    path_entries = [str(tess), str(pop)]
    current_path = os.environ.get("PATH", "")
    if current_path:
        new_path = os.pathsep.join(path_entries + [current_path])
    else:
        new_path = os.pathsep.join(path_entries)
    os.environ["PATH"] = new_path


def _run_migrations(local_root: Path) -> int:
    """Run Alembic migrations against the local database."""
    root = _project_root()
    alembic_ini = root / "alembic.ini"
    db_url = f"sqlite:///{local_root / 'db' / 'taxflow.db'}"
    os.environ.setdefault("DATABASE_URL", db_url)
    os.environ.setdefault("ALEMBIC_CONFIG", str(alembic_ini.resolve()))
    os.environ.setdefault("TAXFLOW_LOCAL_ROOT", str(local_root))
    try:
        from alembic.config import Config
        from alembic import command
        cfg = Config(str(alembic_ini))
        cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(cfg, "head")
        print("[launcher] migrations complete")
        return 0
    except Exception as exc:
        print(f"[launcher] migration failed: {exc}", file=sys.stderr)
        return 1


def _start_server(local_root: Path) -> int:
    root = _project_root()
    os.environ["DATABASE_URL"] = f"sqlite:///{local_root / 'db' / 'taxflow.db'}"
    os.environ["TAXFLOW_LOCAL_ROOT"] = str(local_root)
    os.environ.setdefault("TAXFLOW_ENVIRONMENT", "production")
    os.environ.setdefault("TAXFLOW_RUNTIME_MODE", "offline")
    os.environ.setdefault("TAXFLOW_SINGLE_USER", "true")

    host = os.environ.get("TAXFLOW_HOST", "127.0.0.1")
    port = int(os.environ.get("TAXFLOW_PORT", "8000"))
    url = f"http://{host}:{port}"

    def _open_browser():
        try:
            webbrowser.open(url, new=2)
        except Exception:
            pass

    threading.Timer(1.5, _open_browser).start()

    if getattr(sys, "frozen", False):
        # In a PyInstaller bundle we are the interpreter; run uvicorn in-process.
        print(f"[launcher] starting uvicorn on {url}")
        import uvicorn
        uvicorn.run(
            "backend.api:app",
            host=host,
            port=port,
            log_level="info",
            reload=False,
        )
        return 0

    # Source/dev mode: spawn uvicorn as a subprocess so reload etc. still work.
    cmd = [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", host, "--port", str(port)]
    print(f"[launcher] starting server: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=str(root))
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait(timeout=10)
    return proc.returncode


def main() -> int:
    local_root = _local_root()
    _ensure_dirs(local_root)
    _set_vendor_paths()
    print(f"[launcher] local root: {local_root}")
    print(f"[launcher] project root: {_project_root()}")
    if _run_migrations(local_root) != 0:
        return 1
    return _start_server(local_root)


if __name__ == "__main__":
    sys.exit(main())
