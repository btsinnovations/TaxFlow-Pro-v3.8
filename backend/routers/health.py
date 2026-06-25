"""Health and operational status endpoints.
"""
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Depends, Request

from backend.database import get_db
from backend.local.migration_health import check_migrations
from backend.routers.auth import get_current_user
from backend.local.bootstrap import run_bootstrap

router = APIRouter(prefix="/health", tags=["health"])


def _read_version() -> str:
    """Read the canonical version from the project root."""
    root = Path(__file__).resolve().parents[2]
    version_file = root / "version.txt"
    try:
        return version_file.read_text().strip()
    except FileNotFoundError:
        return "0.0.0"


@router.get("/migrations")
def migration_health(
    _current_user = Depends(get_current_user),
):
    """Return Alembic migration health (authenticated)."""
    return check_migrations()


@router.get("/public")
def public_health():
    """Public liveness probe."""
    return {"status": "ok", "version": _read_version()}


@router.get("/config")
def config_summary(_current_user=Depends(get_current_user)):
    """Return non-sensitive runtime configuration summary."""
    from backend.local import settings
    return {
        "single_user": settings.is_single_user(),
        "multi_entity": getattr(settings, "TAXFLOW_MULTI_ENTITY", False),
        "offline": settings.is_offline(),
        "runtime_mode": settings.RUNTIME_MODE,
    }


@router.get("/bootstrap")
def bootstrap_status():
    """Return the local dependency bootstrap status (no auth required)."""
    report = run_bootstrap()
    return report.to_dict()


@router.get("/echo-auth")
def echo_auth(request: Request):
    """Echo Authorization header and localStorage token status for UI debugging.

    No auth required. Call from browser console with:
        fetch('/api/health/echo-auth').then(r => r.json()).then(console.log)
    """
    auth_header = request.headers.get("authorization")
    return {
        "received_authorization": auth_header,
        "has_authorization": bool(auth_header),
        "authorization_prefix": auth_header.split(" ")[0] if auth_header else None,
    }

