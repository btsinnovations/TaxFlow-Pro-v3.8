"""TaxFlow Pro v3.10 — bulletproof per-test harness.

Every test gets its own isolated in-memory SQLite database.
Schema is created via Base.metadata.create_all() so it always matches the
Current declarative models. Legacy module-level imports (engine,
TestingSessionLocal, override_get_db) are kept as proxies that resolve to the
currently active test's engine/session.
"""

# Disable the OS credential store by default so tests stay deterministic.
class _FailingKeyring:
    def get_password(self, service: str, username: str):
        raise RuntimeError("keyring disabled in tests")

    def set_password(self, service: str, username: str):
        raise RuntimeError("keyring disabled in tests")

    def delete_password(self, service: str, username: str):
        raise RuntimeError("keyring disabled in tests")


# Must happen before backend.auth is imported, otherwise auth.SECRET_KEY would
# be created against the real OS credential store.
from backend.local import keyring_secret

keyring_secret.keyring = _FailingKeyring()


# Ensure tests exercise the single-user default.
import os

os.environ["TAXFLOW_SINGLE_USER"] = "true"
os.environ["TAXFLOW_RUNTIME_MODE"] = "offline"
# Prevent shared production DB or secrets file from leaking into tests.
# Use an in-memory SQLite default for any module-import-time engine creation
# (e.g. backend.api startup migrations), then each test gets its own temp DB.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("TAXFLOW_SECRETS_FILE", None)
# Disable global rate limiting so fast test suites do not hit burst limits.
os.environ["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
os.environ["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"


import base64
import secrets
import sys
from pathlib import Path
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, get_db  # noqa: E402
from backend.api import app  # noqa: E402
from backend import models  # noqa: E402
from backend.models import User  # noqa: E402
from backend.routers.auth import get_password_hash  # noqa: E402

# Disable global API rate limiting in tests; the limiter is imported at module
# load time with production defaults, so mutate its internal state in place
# rather than replacing the module reference (the middleware closure already
# captured the original instance).
import backend.api as _api_module  # noqa: E402
_api_module._GLOBAL_RATE_LIMITER.limit = 10000
_api_module._GLOBAL_RATE_LIMITER.burst = 10000
_api_module._GLOBAL_RATE_LIMITER.window = 1
_api_module._GLOBAL_RATE_LIMITER._windows.clear()


# -----------------------------------------------------------------------------
# Per-test context registry
# -----------------------------------------------------------------------------

from backend.tests._test_context import (
    _TestContext,
    get_active_context as _active_context,
    set_active_context as _set_context,
    active_engine,
    active_sessionlocal,
    active_override_get_db,
)


# -----------------------------------------------------------------------------
# Proxy objects for legacy module-level imports
# -----------------------------------------------------------------------------

class _EngineProxy:
    """Proxy that delegates attribute access to the active test engine."""

    def __getattr__(self, name: str) -> Any:
        return getattr(active_engine(), name)

    def __repr__(self) -> str:
        try:
            return repr(active_engine())
        except RuntimeError:
            return "<_EngineProxy (no active context)>"


class _SessionLocalProxy:
    """Proxy sessionmaker that creates a Session bound to the active engine."""

    def __call__(self, **kwargs: Any) -> Any:
        SessionLocal = active_sessionlocal()
        if kwargs:
            return SessionLocal(**kwargs)
        return SessionLocal()

    def __repr__(self) -> str:
        try:
            return repr(active_sessionlocal())
        except RuntimeError:
            return "<_SessionLocalProxy (no active context)>"


engine: Engine = _EngineProxy()  # type: ignore[assignment]
TestingSessionLocal = _SessionLocalProxy()


def override_get_db() -> Generator[Any, None, None]:
    """Return the active test's DB-override generator."""
    return active_override_get_db()


# -----------------------------------------------------------------------------
# Migration helper
# -----------------------------------------------------------------------------

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _create_schema(engine: Engine) -> None:
    """Create all tables from the current declarative metadata."""
    Base.metadata.create_all(bind=engine)


# -----------------------------------------------------------------------------
# Test user helper (shared by auth_client and seed helpers)
# -----------------------------------------------------------------------------

_TEST_PASSWORD = "T4xFl0…2026"


def _create_test_user(db) -> User:
    user = db.query(User).filter(User.username == "testuser").first()
    if user:
        # Ensure a primary client exists for single-user tenant resolution.
        has_client = db.query(models.Client).filter(
            models.Client.user_id == user.id
        ).first() is not None
        if not has_client:
            client = models.Client(name="Test Client", user_id=user.id)
            db.add(client)
            db.commit()
        return user
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash(_TEST_PASSWORD),
        is_active=True,
        encryption_salt=base64.b64encode(secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    client = models.Client(name="Test Client", user_id=user.id)
    db.add(client)
    db.commit()
    return user


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient backed by a fresh per-test SQLite database."""
    db_url = "sqlite:///:memory:"

    test_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Attach SQLite pragma / integrity hooks before creating any connection.
    from backend.database import _set_sqlite_pragmas, _sqlite_integrity_check
    event.listen(test_engine, "connect", _set_sqlite_pragmas)
    event.listen(test_engine, "connect", _sqlite_integrity_check)

    _create_schema(test_engine)

    TestSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    def _override_get_db() -> Generator[Any, None, None]:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        ctx = _TestContext(
            engine=test_engine,
            SessionLocal=TestSessionLocal,
            override_get_db=_override_get_db,
            client=test_client,
            db_url=db_url,
        )
        _set_context(ctx)
        try:
            yield test_client
        finally:
            _set_context(None)

    app.dependency_overrides.pop(get_db, None)
    test_engine.dispose()


@pytest.fixture(scope="function")
def db(client: TestClient) -> Generator[Any, None, None]:
    """Provide a SQLAlchemy Session tied to the current test database."""
    db_gen = override_get_db()
    session = next(db_gen)
    try:
        yield session
    finally:
        session.close()
        try:
            next(db_gen)
        except StopIteration:
            pass


@pytest.fixture(scope="function")
def auth_client(client: TestClient) -> TestClient:
    """Return a fresh TestClient authenticated as the shared test user."""
    from backend.auth_rate_limit import reset_attempts

    db_gen = override_get_db()
    db = next(db_gen)
    try:
        user = _create_test_user(db)
        username = user.username  # capture scalar while still bound
    finally:
        db.close()
        try:
            next(db_gen)
        except StopIteration:
            pass

    reset_attempts(username)

    resp = client.post("/api/auth/login", data={
        "username": username,
        "password": _TEST_PASSWORD,
    })
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    # Do not mutate the shared ``client`` fixture; yield a new TestClient with
    # the Authorization header set. Both clients share the same app/override.
    authed_client = TestClient(app)
    authed_client.headers.update({"Authorization": f"Bearer {token}"})
    return authed_client
