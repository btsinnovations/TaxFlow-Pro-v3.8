"""Disable the OS credential store by default so tests stay deterministic
and do not write real secrets. Individual tests can opt into an in-memory
keyring backend when exercising TASK-013 behavior.
"""


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


import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Base, get_db
from backend.api import app
from backend.models import User
from backend.routers.auth import get_password_hash


TEST_DB = "sqlite:///./test_taxflow.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Some tests import the model classes before the client fixture creates the
# schema. Make sure the in-memory test DB is current with any migration-only
# columns (e.g. txn_uid, import_source) that are not in the baseline.
def _ensure_test_schema():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass


_ensure_test_schema()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


import base64
import secrets


# Shared test password. Must match what auth_client sends to /api/auth/login.
_TEST_PASSWORD = "T4xFl0w!T3st-Us3r-2026"


def _create_test_user(db):
    user = db.query(User).filter(User.username == "testuser").first()
    if user:
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
    return user


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def auth_client(client):
    from backend.auth_rate_limit import reset_attempts
    db = TestingSessionLocal()
    try:
        user = _create_test_user(db)
    finally:
        db.close()

    # Reset brute-force tracker for the shared test user so failures in earlier
    # tests do not lock out this fixture.
    reset_attempts(user.username)

    resp = client.post("/api/auth/login", data={
        "username": user.username,
        "password": _TEST_PASSWORD,
    })
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return client
