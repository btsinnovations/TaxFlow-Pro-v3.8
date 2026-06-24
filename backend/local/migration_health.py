"""Alembic migration health check utilities.

Exposes a deterministic way to compare the revision currently applied to the
database against the latest revision available in the Alembic script directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine


def _get_db_url(db_url: Optional[str] = None) -> str:
    from backend.database import DATABASE_URL
    return db_url or DATABASE_URL


def _get_alembic_config(db_url: Optional[str] = None) -> Config:
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", _get_db_url(db_url))
    return cfg


def _walk_upwards(script: ScriptDirectory, current_rev: str, latest_rev: str) -> list[str]:
    """Return the ordered list of revisions from current (exclusive) to latest (inclusive)."""
    pending = []
    seen = set()
    current = current_rev
    while current != latest_rev:
        rev = script.get_revision(current)
        if not rev.nextrev:
            break
        # Choose a single next revision; handle merge points deterministically.
        next_rev = sorted(rev.nextrev)[0]
        if next_rev in seen:
            break
        seen.add(next_rev)
        pending.append(next_rev)
        current = next_rev
    return pending


def check_migrations(db_url: Optional[str] = None) -> dict:
    """Return migration health.

    Returns a dict with keys:
        current: revision currently stamped in the DB (or None).
        latest:  head revision from the Alembic script directory.
        pending: list of revision ids between current and latest (exclusive of current).
        ok:      True when current == latest and no migrations are pending.
    """
    cfg = _get_alembic_config(db_url)
    script = ScriptDirectory.from_config(cfg)

    engine = create_engine(_get_db_url(db_url))
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()

    latest_rev = script.get_current_head()
    if current_rev is None:
        # No migrations applied yet; everything is pending.
        pending = list(reversed([r.revision for r in script.walk_revisions()]))
    elif current_rev != latest_rev:
        pending = _walk_upwards(script, current_rev, latest_rev)
    else:
        pending = []

    return {
        "current": current_rev,
        "latest": latest_rev,
        "pending": pending,
        "ok": current_rev == latest_rev,
    }
