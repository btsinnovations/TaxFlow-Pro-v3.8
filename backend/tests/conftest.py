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
os.environ["TAXFLOW_TESTING"] = "true"


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
# load time with production defaults. Mutating limits is fragile, so replace the
# check method with a no-op to guarantee tests never hit 429s.
import backend.api as _api_module  # noqa: E402
_api_module._GLOBAL_RATE_LIMITER.check = lambda remote_addr, headers: None
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
        if not user.clients:
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


@pytest.fixture(scope="function", autouse=True)
def reset_global_rate_limiter():
    """Ensure a clean default rate limiter for every test."""
    from backend import api
    from backend.rate_limit import GlobalRateLimiter

    api._GLOBAL_RATE_LIMITER = GlobalRateLimiter(
        limit=100,
        window=60,
        burst=10,
        trusted_proxy_hops=0,
    )
    # Default instance: allow the test bypass in middleware to work so login
    # fixtures across the suite do not trip rate limits.
    api._GLOBAL_RATE_LIMITER._test_enforce = False
    yield
    # Re-enable the test bypass for all other tests by clearing the enforcement
    # sentinel; rate-limit tests that need enforcement set it explicitly.
    api._GLOBAL_RATE_LIMITER._test_enforce = False


@pytest.fixture(scope="function")
def auth_client(client: TestClient) -> TestClient:
    """Return a fresh TestClient authenticated as the shared test user."""
    from backend.auth_rate_limit import reset_attempts

    db_gen = override_get_db()
    db = next(db_gen)
    try:
        user = _create_test_user(db)
        # Ensure relationship is loaded so resolve_user_tenant_id can pick the client.
        db.refresh(user, ["clients"])
        username = user.username
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


# -----------------------------------------------------------------------------
# v3.11.6 Track 1 — New fixtures for tenant/role/PostgreSQL testing
# -----------------------------------------------------------------------------

import base64 as _b64
import secrets as _secrets


def _create_test_tenant(db, name: str = "Bundle Tenant"):
    """Create a User + Client pair and return the Client (tenant)."""
    user = models.User(
        username=f"tenant_{name.lower().replace(' ', '_')}",
        email=f"{name.lower().replace(' ', '_')}@example.com",
        hashed_password=get_password_hash(_TEST_PASSWORD),
        is_active=True,
        encryption_salt=_b64.b64encode(_secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    client = models.Client(name=name, user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _create_user_with_role(db, tenant, role: str = "viewer", username: str = None):
    """Create a User, assign them a role on the given tenant (Client), and return (User, Membership)."""
    from backend.local.roles import Role, set_role

    if username is None:
        username = f"{role}_{tenant.name.lower().replace(' ', '_')}"
    user = models.User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(_TEST_PASSWORD),
        is_active=True,
        encryption_salt=_b64.b64encode(_secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    role_enum = Role[role] if isinstance(role, str) else role
    membership = set_role(db, user.id, tenant.id, role_enum, actor_user_id=tenant.user_id)
    return user, membership


@pytest.fixture(scope="function")
def tenant(db):
    """Return a seeded Client (tenant) for bundle tests."""
    return _create_test_tenant(db, name="Bundle Tenant")


@pytest.fixture(scope="function")
def viewer_member(db, tenant):
    """Return (User, Membership) with viewer role on the tenant."""
    return _create_user_with_role(db, tenant, role="viewer")


@pytest.fixture(scope="function")
def admin_member(db, tenant):
    """Return (User, Membership) with admin role on the tenant."""
    return _create_user_with_role(db, tenant, role="admin")


def switch_profile(client: TestClient, profile_id: int) -> None:
    """Switch the active tenant/profile for multi-tenant tests.

    Sets the X-Profile-Id header so subsequent requests are scoped to the
    given profile/tenant.
    """
    client.headers.update({"X-Profile-Id": str(profile_id)})


# -----------------------------------------------------------------------------
# Optional PostgreSQL test fixture for native RLS validation
# -----------------------------------------------------------------------------

@pytest.fixture(scope="class")
def postgres_client(request):
    """Yield a TestClient backed by a live PostgreSQL database.

    Reads TEST_DATABASE_URL from the environment. If not set, the entire
    test class is skipped. When set, the fixture:
      1. Creates a fresh schema
      2. Runs Base.metadata.create_all()
      3. Yields a TestClient
      4. Drops all tables after the test class completes
    """
    db_url = os.environ.get("TEST_DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set; skipping PostgreSQL RLS tests")
        return  # unreachable but keeps type checkers happy

    from sqlalchemy import create_engine as _pg_create_engine
    from sqlalchemy.orm import sessionmaker as _pg_sessionmaker

    pg_engine = _pg_create_engine(db_url, pool_pre_ping=True)

    # Create schema from current models
    Base.metadata.create_all(bind=pg_engine)

    PgSessionLocal = _pg_sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)

    def _pg_override_get_db():
        db = PgSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _pg_override_get_db

    with TestClient(app) as pg_test_client:
        ctx = _TestContext(
            engine=pg_engine,
            SessionLocal=PgSessionLocal,
            override_get_db=_pg_override_get_db,
            client=pg_test_client,
            db_url=db_url,
        )
        _set_context(ctx)
        try:
            yield pg_test_client
        finally:
            _set_context(None)

    app.dependency_overrides.pop(get_db, None)

    # Clean up: drop all tables
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()
