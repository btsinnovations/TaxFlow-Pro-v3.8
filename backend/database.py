import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

from backend.local import sqlcipher_engine as _sqlcipher
from backend.local.secrets_loader import get_secret

# Load environment variables from project root .env if present
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BASE_DIR, ".env"))


def _default_database_url() -> str:
    """Return a default database URL that places the DB in LOCAL_ROOT.

    If TAXFLOW_LOCAL_ROOT is set, use ``<LOCAL_ROOT>/db/taxflow.db``.
    Otherwise fall back to the legacy project-root relative path for dev/tests.
    """
    local_root = os.environ.get("TAXFLOW_LOCAL_ROOT", "").strip()
    if local_root:
        return f"sqlite:///{Path(local_root).resolve() / 'db' / 'taxflow.db'}"
    return "sqlite:///./taxflow.db"


DATABASE_URL = get_secret(
    "DATABASE_URL",
    os.environ.get("DATABASE_URL", _default_database_url()),
)


# SQLCipher encryption configuration (3.3 local-first encryption layer).
# Plain SQLite remains the default for development/tests; production local
# installs set DATABASE_URL=sqlcipher:///... and TAXFLOW_DB_PASSWORD.
SQLCIPHER_ENABLED = DATABASE_URL.startswith("sqlcipher:///")
SQLCIPHER_PASSWORD = get_secret("TAXFLOW_DB_PASSWORD", os.environ.get("TAXFLOW_DB_PASSWORD", ""))
SQLCIPHER_KEYFILE = get_secret("TAXFLOW_DB_KEYFILE", os.environ.get("TAXFLOW_DB_KEYFILE", None))
SQLCIPHER_KEYRING = get_secret("TAXFLOW_DB_KEYRING_TOKEN", os.environ.get("TAXFLOW_DB_KEYRING_TOKEN", None))


def _sqlite_wal_pragma(dbapi_conn, connection_record):
    """Enable WAL mode, busy timeout, and foreign keys for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _make_engine():
    """Create the SQLAlchemy engine based on DATABASE_URL."""
    if DATABASE_URL.startswith("postgresql://"):
        return create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"options": "-c timezone=utc"},
        )

    if SQLCIPHER_ENABLED:
        if not SQLCIPHER_PASSWORD:
            raise ValueError(
                "DATABASE_URL uses sqlcipher:/// but TAXFLOW_DB_PASSWORD is not set"
            )
        keyfile_path = None
        if SQLCIPHER_KEYFILE:
            from pathlib import Path
            keyfile_path = Path(SQLCIPHER_KEYFILE).expanduser()
        keyring_token = SQLCIPHER_KEYRING.encode("utf-8") if SQLCIPHER_KEYRING else None
        return _sqlcipher.create_sqlcipher_engine(
            DATABASE_URL,
            SQLCIPHER_PASSWORD,
            keyfile_path=keyfile_path,
            keyring_token=keyring_token,
        )

    if not DATABASE_URL.startswith("sqlite"):
        raise ValueError(
            "DATABASE_URL must start with sqlite://, sqlcipher:/// or postgresql://"
        )
    return create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )


def _check_postgres_role_security(engine):
    """Refuse multi-tenant PostgreSQL if the DB role bypasses RLS.

    PostgreSQL superusers and roles with BYPASSRLS ignore RLS even when
    ALTER TABLE ... FORCE ROW LEVEL SECURITY is set. In multi-tenant mode
    this silently voids tenant isolation, so we fail fast at startup.
    """
    # Single-user SQLite mode does not use PostgreSQL; skip.
    if not DATABASE_URL.startswith("postgresql://"):
        return

    # Single-user PostgreSQL mode does not enforce tenant isolation; skip.
    # Import here to avoid circular imports at module load time.
    from backend.local import settings as local_settings
    if local_settings.is_single_user():
        return

    with engine.connect() as conn:
        from sqlalchemy import text
        role = conn.execute(text("SELECT current_user")).scalar()
        result = conn.execute(
            text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :role"
            ),
            {"role": role},
        ).fetchone()

    if result is None:
        raise RuntimeError(
            f"PostgreSQL role '{role}' not found in pg_roles; cannot verify RLS safety."
        )

    rolsuper, rolbypassrls = result
    if rolsuper:
        raise RuntimeError(
            f"TaxFlow multi-tenant mode cannot run with PostgreSQL superuser role '{role}'. "
            "RLS is bypassed for superusers, so tenant isolation would be void. "
            "Use a non-superuser role with BYPASSRLS disabled."
        )
    if rolbypassrls:
        raise RuntimeError(
            f"TaxFlow multi-tenant mode cannot run with PostgreSQL role '{role}' "
            "because it has BYPASSRLS. Tenant isolation would be void."
        )


engine = _make_engine()
_check_postgres_role_security(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

if SQLCIPHER_ENABLED:
    # SQLCipher uses page-level encryption; WAL and some SQLite pragmas behave
    # differently. Keep foreign-key enforcement.
    def _sqlcipher_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from sqlalchemy import event
    event.listen(engine, "connect", _sqlcipher_pragma)
elif not DATABASE_URL.startswith("postgresql://"):
    from sqlalchemy import event
    event.listen(engine, "connect", _sqlite_wal_pragma)
    # Integrity check listener is defined below; applied after Base creation.

Base = declarative_base()


# ---------------------------------------------------------------------------
# SQLite reliability helpers (TASK-038.11)
# ---------------------------------------------------------------------------

def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Enable WAL, busy timeout, and foreign keys on every SQLite connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _sqlite_integrity_check(dbapi_conn, connection_record):
    """Run PRAGMA integrity_check and raise if the DB is corrupt."""
    try:
        cursor = dbapi_conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
    except Exception as exc:
        raise RuntimeError(f"SQLite integrity check failed: {exc}") from exc
    if result != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {result}")


# Apply integrity check listener now that the helper is defined.
if not SQLCIPHER_ENABLED and not DATABASE_URL.startswith("postgresql://"):
    from sqlalchemy import event
    event.listen(engine, "connect", _sqlite_integrity_check)


def recover_sqlite_db(db_path: str | Path, target_path: str | Path | None = None) -> Path:
    """Best-effort crash recovery: dump/restore a SQLite DB to a fresh file.

    This is a local-only operation with no network access. The new file is
    verified with PRAGMA integrity_check before return.
    """
    db_path = Path(db_path)
    target = Path(target_path) if target_path else db_path.parent / f"{db_path.stem}_recovered{db_path.suffix}"
    target.unlink(missing_ok=True)
    source = sqlite3.connect(str(db_path))
    try:
        dest = sqlite3.connect(str(target))
        try:
            with dest:
                for line in source.iterdump():
                    if line.startswith("PRAGMA foreign_keys=OFF;"):
                        continue
                    dest.execute(line)
            integrity = dest.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"Recovered database failed integrity check: {integrity}")
        finally:
            dest.close()
    finally:
        source.close()
    return target


# Install RLS connection listeners when running on PostgreSQL.
# Done here rather than api.py to cover imports from scripts/routers.
try:
    from .rls import install_rls_event_listeners
    install_rls_event_listeners()
except Exception:
    # If rls.py imports fail (e.g., missing psycopg2), dev SQLite continues.
    pass


# Install append-only audit-entry triggers and listeners.
try:
    from .audit.append_only import install_append_only_triggers
    install_append_only_triggers(engine)
except Exception:
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
