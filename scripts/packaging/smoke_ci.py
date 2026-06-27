"""Lightweight CI smoke test for production-mode packaging.

This script does not run the full PyInstaller build. Instead it:

1. Builds the frontend (so ``frontend/dist`` exists for static serving).
2. Starts the backend with ``TAXFLOW_ENV=production`` against a temporary
   SQLite database.
3. Confirms ``/api/tests/`` returns 404.
4. Confirms ``/api/health`` reports ``production_mode: true``.

Exit codes:
- 0: all checks passed
- non-zero: at least one check failed or the server failed to start
"""
from __future__ import annotations

import os
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

# Ensure backend imports resolve when this script is run from scripts/packaging.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://127.0.0.1:8123"


import shutil

# ... existing imports


def _run_frontend_build() -> bool:
    """Build the frontend so static assets exist."""
    print("[ci-smoke] building frontend...")
    frontend = PROJECT_ROOT / "frontend"
    if not (frontend / "package.json").exists():
        print("[ci-smoke] SKIP: frontend/package.json not found")
        return False
    npm = shutil.which("npm")
    if not npm:
        print("[ci-smoke] SKIP: npm not found on PATH")
        return False
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=str(frontend),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("[ci-smoke] frontend build failed:")
        print(result.stdout)
        print(result.stderr)
        return False
    print("[ci-smoke] frontend build OK")
    return True


def _wait_for_server(timeout: int = 90) -> bool:
    """Poll the health endpoint until it responds."""
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                print("[ci-smoke] server healthy")
                return True
        except Exception as exc:
            last_error = str(exc)
        time.sleep(1)
    print(f"[ci-smoke] server did not become healthy in time ({last_error})")
    return False


def _start_server(db_path: Path) -> subprocess.Popen:
    """Start uvicorn in production mode on a temporary database."""
    env = os.environ.copy()
    env["TAXFLOW_ENV"] = "production"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["TAXFLOW_LOCAL_ROOT"] = str(db_path.parent)
    env["UVICORN_HOST"] = "127.0.0.1"
    env["UVICORN_PORT"] = "8123"
    env["TAXFLOW_TESTING"] = "true"
    env["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
    env["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
    env["TAXFLOW_SINGLE_USER"] = "true"
    env["TAXFLOW_RUNTIME_MODE"] = "offline"
    # Point Alembic at the repo's alembic.ini so migrations resolve.
    env["ALEMBIC_CONFIG"] = str(PROJECT_ROOT / "alembic.ini")

    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "8123", "--log-level", "info"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def main() -> int:
    """Run the lightweight CI smoke test and return an exit code."""
    if not _run_frontend_build():
        return 1

    with tempfile.TemporaryDirectory(prefix="taxflow-smoke-") as tmp:
        db_path = Path(tmp) / "taxflow.db"
        proc = _start_server(db_path)
        try:
            if not _wait_for_server():
                return 1

            # 1) /api/tests/ must 404 in production.
            r = requests.get(f"{BASE_URL}/api/tests/", timeout=10)
            print(f"[ci-smoke] GET /api/tests/ -> {r.status_code}")
            if r.status_code != 404:
                print("[ci-smoke] FAIL: /api/tests/ did not return 404 in production")
                return 1

            # 2) /api/health must report production_mode: true.
            r = requests.get(f"{BASE_URL}/api/health", timeout=10)
            print(f"[ci-smoke] GET /api/health -> {r.status_code}")
            if r.status_code != 200:
                print("[ci-smoke] FAIL: /api/health did not return 200")
                return 1
            data = r.json()
            if data.get("production_mode") is not True:
                print(f"[ci-smoke] FAIL: production_mode is {data.get('production_mode')!r}")
                return 1
            if data.get("environment") != "production":
                print(f"[ci-smoke] FAIL: environment is {data.get('environment')!r}")
                return 1

            # 3) Top-level /health must also report production_mode: true.
            r = requests.get(f"{BASE_URL}/health", timeout=10)
            data = r.json()
            if data.get("production_mode") is not True:
                print(f"[ci-smoke] FAIL: top-level health production_mode is {data.get('production_mode')!r}")
                return 1

            print("[ci-smoke] all production-mode checks passed")
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    sys.exit(main())
