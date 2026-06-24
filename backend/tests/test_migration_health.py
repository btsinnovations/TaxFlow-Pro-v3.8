"""Tests for DATA-02 migration health check."""
from __future__ import annotations

import tempfile

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from backend.local.migration_health import check_migrations


def _current_head() -> str:
    """Return the current Alembic head revision from the project scripts."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    return script.get_current_head()


def test_fresh_db_reports_current_equals_head():
    head = _current_head()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_url = f"sqlite:///{tmp}/test.db"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:head)"), {"head": head})
            conn.commit()
        engine.dispose()

        result = check_migrations(db_url)

        assert result["current"] == head
        assert result["latest"] == head
        assert result["pending"] == []
        assert result["ok"] is True


def test_stale_revision_reports_pending():
    head = _current_head()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_url = f"sqlite:///{tmp}/test.db"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('d75a7eba9fd0')"))
            conn.commit()
        engine.dispose()

        result = check_migrations(db_url)

        assert result["current"] == "d75a7eba9fd0"
        assert result["latest"] == head
        assert result["pending"]
        assert result["ok"] is False
