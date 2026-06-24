"""Append-only audit entry enforcement helpers.

TaxFlow Pro v3.9.2 makes audit entries immutable. This module provides:
- SQLAlchemy event listeners that block UPDATE and DELETE on audit_entries.
- Database-level AFTER UPDATE / AFTER DELETE triggers for SQLite and PostgreSQL
  so the protection survives direct SQL / schema introspection.
- A management-only escape hatch (``_set_audit_entry_mutable``) for migrations.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine

from ..database import DATABASE_URL as _DATABASE_URL


_APPEND_ONLY_TABLE = "audit_entries"


def _is_postgres(dbapi_conn=None) -> bool:
    """Return True if the current connection/env targets PostgreSQL."""
    if _DATABASE_URL and _DATABASE_URL.startswith("postgresql://"):
        return True
    if dbapi_conn is not None:
        module = getattr(dbapi_conn, "__class__", None)
        if module is not None:
            module = getattr(module, "__module__", "")
            if module and module.startswith("psycopg2"):
                return True
    return False


def _append_only_sqlite() -> list[str]:
    """Return SQLite AFTER UPDATE/DELETE trigger SQL as separate statements."""
    return [
        f"""
CREATE TRIGGER IF NOT EXISTS trg_audit_entries_prevent_update
AFTER UPDATE ON {_APPEND_ONLY_TABLE}
FOR EACH ROW
WHEN NOT (OLD.chain_hash IS NULL AND NEW.chain_hash IS NOT NULL AND
          OLD.signature IS NULL AND NEW.signature IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'audit_entries is append-only: updates are forbidden');
END;
""".strip(),
        f"""
CREATE TRIGGER IF NOT EXISTS trg_audit_entries_prevent_delete
AFTER DELETE ON {_APPEND_ONLY_TABLE}
BEGIN
    SELECT RAISE(ABORT, 'audit_entries is append-only: deletes are forbidden');
END;
""".strip(),
    ]


def _append_only_postgres() -> str:
    """Return PostgreSQL AFTER UPDATE/DELETE trigger function + triggers."""
    return f"""
CREATE OR REPLACE FUNCTION audit_entries_prevent_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        IF (OLD.chain_hash IS NULL AND NEW.chain_hash IS NOT NULL AND
            OLD.signature IS NULL AND NEW.signature IS NOT NULL) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'audit_entries is append-only: % on audit_entries are forbidden', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_entries_prevent_update ON {_APPEND_ONLY_TABLE};
DROP TRIGGER IF EXISTS trg_audit_entries_prevent_delete ON {_APPEND_ONLY_TABLE};

CREATE TRIGGER trg_audit_entries_prevent_update
AFTER UPDATE ON {_APPEND_ONLY_TABLE}
FOR EACH ROW EXECUTE FUNCTION audit_entries_prevent_mutation();

CREATE TRIGGER trg_audit_entries_prevent_delete
AFTER DELETE ON {_APPEND_ONLY_TABLE}
FOR EACH ROW EXECUTE FUNCTION audit_entries_prevent_mutation();
"""


def _has_table(conn: Connection, table_name: str) -> bool:
    """Check whether ``table_name`` exists in the current database."""
    raw_conn = conn.connection.dbapi_connection
    if raw_conn is None:
        return False
    if _is_postgres(raw_conn):
        with raw_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s AND table_schema = 'public'",
                (table_name,),
            )
            return bool(cur.fetchone())
    # SQLite fallback — sqlite3.Cursor does not support context manager protocol.
    cur = raw_conn.cursor()
    try:
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return bool(cur.fetchone())
    finally:
        cur.close()


def install_append_only_triggers(engine: Engine) -> None:
    """Create AFTER UPDATE/DELETE triggers on ``audit_entries``.

    Called automatically via the ``connect`` event on SQLite, and should be
    invoked from an Alembic migration for PostgreSQL (where a database-level
    trigger function is required).
    """
    with engine.begin() as conn:
        if not _has_table(conn, _APPEND_ONLY_TABLE):
            return
        if _is_postgres(conn.connection.dbapi_connection):
            conn.exec_driver_sql(_append_only_postgres())
        else:
            # SQLite trigger bodies contain semicolons; use executescript so the
            # entire block is parsed as one statement.
            for stmt in _append_only_sqlite():
                conn.exec_driver_sql(stmt)


@event.listens_for(Engine, "connect")
def _sqlite_auto_install_append_only_triggers(dbapi_conn: Any, connection_record: Any) -> None:
    """On every SQLite connection, ensure the audit_entries triggers exist."""
    if _is_postgres(dbapi_conn):
        return
    try:
        cursor = dbapi_conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_APPEND_ONLY_TABLE,))
        if not cursor.fetchone():
            cursor.close()
            return
        cursor.executescript(";\n".join(_append_only_sqlite()))
    except Exception:
        # Fail open: if audit_entries is missing (e.g., during tests), ignore.
        pass


def _is_audit_entry_table_name(table_name: str) -> bool:
    # SQLAlchemy 2.x passes a string; 1.x may pass an object.
    if hasattr(table_name, "name"):
        table_name = table_name.name
    return table_name == _APPEND_ONLY_TABLE


@event.listens_for(Engine, "before_cursor_execute")
def _block_audit_entries_update_delete(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    """Client-side guard: abort UPDATE/DELETE against audit_entries at the driver level.

    This catches raw SQL, Alembic downgrade drift, and ORM flush events that
    bypass the instance-level event listener. It is intentionally simple and
    permissive for connection pragmas and other system statements.

    The audit-trail ``record()`` function uses ``_set_audit_entries_mutable()``
    to allow the single legitimate UPDATE that sets the chain_hash for a freshly
    inserted row.
    """
    global _audit_entries_mutable
    if _audit_entries_mutable:
        return
    upper = statement.strip().upper()
    # Allow Alembic's own version table operations and trigger/schema introspection.
    if upper.startswith("SELECT ") or upper.startswith("PRAGMA ") or upper.startswith("CREATE ") or upper.startswith("DROP "):
        return
    # INSERT into audit_entries is always allowed (append-only).
    if upper.startswith("INSERT") and "AUDIT_ENTRIES" in upper:
        return
    # Permit the chain_hash self-UPDATE generated by ORM persistence within the
    # audit record function. It is a single-column update keyed by primary key.
    if upper.startswith("UPDATE") and "AUDIT_ENTRIES" in upper:
        if "CHAIN_HASH" in upper:
            return
        raise Exception("audit_entries is append-only: UPDATE is forbidden")
    if upper.startswith("DELETE") and "FROM" in upper and "AUDIT_ENTRIES" in upper:
        raise Exception("audit_entries is append-only: DELETE is forbidden")


# Global flag used by the management context manager.
_audit_entries_mutable = False


@contextmanager
def _set_audit_entries_mutable():
    """Context manager that temporarily allows UPDATE/DELETE on audit_entries.

    This is intended ONLY for migrations and administrative chain backfills.
    Normal application code must never use it.
    """
    global _audit_entries_mutable
    old = _audit_entries_mutable
    _audit_entries_mutable = True
    try:
        yield
    finally:
        _audit_entries_mutable = old
