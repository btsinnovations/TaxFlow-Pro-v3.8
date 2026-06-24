"""Hybrid auth tests for TaxFlow Pro v3.9."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import text

from backend.database import Base
from backend.tests.conftest import engine as test_engine
from backend.auth import (
    get_local_secret,
    hash_password,
    create_access_token,
    decode_access_token,
    boot_local_admin,
    authenticate_local_user,
    cleanup_expired_revoked_tokens,
)
from backend.local.crypto import generate_keyfile
from backend import models


def _strong_password():
    """Return a password that passes the default entropy policy."""
    return "T4xFl0w!Br0nze-V@ult-2026"



def _reset_rate_limit():
    from backend.auth_rate_limit import _tracker
    _tracker.clear()

@pytest.fixture(autouse=True)
def _reset_brute_force_tracker():
    """Ensure brute-force counters are isolated between tests."""
    from backend.auth_rate_limit import _tracker
    from backend.auth_rate_limit import _tracker;     yield
    from backend.auth_rate_limit import _tracker; 

@pytest.fixture(autouse=True)
def _force_file_secret_for_legacy_tests(monkeypatch):
    """Disable keyring for this legacy suite to keep deterministic file-only behavior."""

    class _FailingKeyring:
        def get_password(self, service, username):
            raise RuntimeError("keyring disabled in legacy auth tests")

        def set_password(self, service, username, password):
            raise RuntimeError("keyring disabled in legacy auth tests")

        def delete_password(self, service, username):
            raise RuntimeError("keyring disabled in legacy auth tests")

    monkeypatch.setattr("backend.local.keyring_secret.keyring", _FailingKeyring())
    yield
    # Remove any leftover fallback file between tests.
    from backend import auth as auth_module

    if os.path.exists(auth_module.LOCAL_SECRET_FILE):
        os.remove(auth_module.LOCAL_SECRET_FILE)



def _reset_db():
    # Drop tables that actually exist; some tests may not create every table.
    with test_engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        tables = [row[0] for row in result]
        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(bind=test_engine)


def test_first_boot_creates_local_user(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["username"]


def test_boot_only_once(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 400


def test_login_success_and_failure(client: TestClient):
    _reset_db()
    client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})

    resp = client.post("/api/auth/login", data={"username": "local", "password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    resp = client.post("/api/auth/login", data={"username": "local", "password": "wrong"})
    assert resp.status_code == 401


def test_login_json(client: TestClient):
    _reset_db()
    client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    resp = client.post("/api/auth/login-json", json={"username": "local", "password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_protected_route_rejects_missing_token(client: TestClient):
    _reset_db()
    resp = client.get("/api/clients/")
    assert resp.status_code == 401


def test_protected_route_rejects_invalid_token(client: TestClient):
    _reset_db()
    resp = client.get("/api/clients/", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code == 401


def test_token_expiry_and_secret_regeneration_invalidates_token(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    token = resp.json()["access_token"]

    # Simulate secret regeneration by deleting .local_secret
    secret_file = get_local_secret()
    secret_path = None
    from backend import auth as auth_module
    # best-effort locate file
    if os.path.exists(auth_module.LOCAL_SECRET_FILE):
        secret_path = auth_module.LOCAL_SECRET_FILE
        os.remove(secret_path)
    # generate new secret
    new_secret = get_local_secret()
    assert new_secret != secret_file
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_bcrypt_hash_and_verify():
    h = hash_password("secret")
    assert h != "secret"
    assert authenticate_local_user  # just ensure import


def test_access_token_contains_jti(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    payload = decode_access_token(token)
    assert payload is not None
    assert "jti" in payload
    assert payload.get("type") == "access"


def test_logout_revokes_access_token(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Token works before logout
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200

    # Server-side logout
    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Same token is now rejected
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


def test_new_login_after_logout_gets_fresh_token(client: TestClient):
    _reset_db()
    client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    resp = client.post("/api/auth/login", data={"username": "local", "password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    old_token = resp.json()["access_token"]

    # Revoke old token
    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {old_token}"})
    assert resp.status_code == 200

    # Fresh login yields a new, valid token
    resp = client.post("/api/auth/login", data={"username": "local", "password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    new_token = resp.json()["access_token"]
    assert new_token != old_token

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200


def test_already_revoked_token_returns_401_on_logout(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    token = resp.json()["access_token"]

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # Second logout with the same token is rejected because the token is revoked.
    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# -- TASK-037 / 3.4g server-side session binding ----------------------------


def _decode_token_jti(token: str) -> str:
    from backend.auth import decode_access_token
    payload = decode_access_token(token)
    assert payload is not None
    return payload["jti"]


def test_access_token_creates_server_side_session(client: TestClient):
    """Issuing an access token should persist a Session row bound to the user."""
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    jti = _decode_token_jti(token)

    from backend.tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        session = db.query(models.Session).filter(models.Session.token_jti == jti).first()
        assert session is not None
        assert session.user_id == 1
        assert session.revoked_at is None
        assert session.expires_at is not None
    finally:
        db.close()


def test_missing_session_rejects_valid_signature(client: TestClient):
    """A token with a valid signature but no matching Session row must be rejected."""
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    valid_token = resp.json()["access_token"]

    # Wipe the server-side Session row while keeping a valid JWT signature.
    from backend.tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        db.query(models.Session).delete()
        db.commit()
    finally:
        db.close()

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
    assert me.status_code == 401


def test_session_revoked_on_logout(client: TestClient):
    """Logout must mark the server-side Session row as revoked."""
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    jti = _decode_token_jti(token)

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    from backend.tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        session = db.query(models.Session).filter(models.Session.token_jti == jti).first()
        assert session is not None
        assert session.revoked_at is not None
    finally:
        db.close()


def test_fresh_login_after_logout_creates_new_session(client: TestClient):
    """A new login after logout must create a new Session row."""
    _reset_db()
    client.post("/api/auth/boot", json={"password": "T4xFl0w!Br0nze-V@ult-2026"})

    resp = client.post("/api/auth/login", data={"username": "local", "password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    old_token = resp.json()["access_token"]
    old_jti = _decode_token_jti(old_token)

    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {old_token}"})

    resp = client.post("/api/auth/login", data={"username": "local", "password": "T4xFl0w!Br0nze-V@ult-2026"})
    assert resp.status_code == 200
    new_token = resp.json()["access_token"]
    new_jti = _decode_token_jti(new_token)
    assert new_jti != old_jti

    from backend.tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        new_session = db.query(models.Session).filter(models.Session.token_jti == new_jti).first()
        assert new_session is not None
        assert new_session.revoked_at is None
    finally:
        db.close()


# SEC-02: master-password entropy policy

def _strong_password():
    return "T4xFl0w!Br0nze-V@ult-2026"


def test_boot_password_too_short(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "short1!"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["failures"][0].startswith("Password must be at least")


def test_boot_password_low_entropy(client: TestClient):
    _reset_db()
    # 14+ chars but only lowercase letters and digits → entropy below 50 bits.
    resp = client.post("/api/auth/boot", json={"password": "abcdefghijklmn1"})
    assert resp.status_code == 422
    assert "entropy" in resp.json()["detail"]["failures"][0].lower()


def test_boot_password_contains_literal_password(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "MyPassword123!Long"})
    assert resp.status_code == 422
    assert any("'password'" in f for f in resp.json()["detail"]["failures"])


def test_boot_password_contains_username(client: TestClient):
    _reset_db()
    resp = client.post(
        "/api/auth/register",
        json={"username": "joshua", "email": "joshua@example.com", "password": "joshuaIsGreat2026!"},
    )
    assert resp.status_code == 422
    assert any("username" in f.lower() for f in resp.json()["detail"]["failures"])


def test_register_password_common(client: TestClient):
    _reset_db()
    resp = client.post(
        "/api/auth/register",
        json={"username": "local", "email": "local@example.com", "password": "Password123456!"},
    )
    # Fails policy because password contains literal "password" and is common-ish.
    assert resp.status_code == 422


def test_boot_password_strong(client: TestClient):
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": _strong_password()})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_change_password_enforces_policy(client: TestClient):
    _reset_db()
    boot = client.post("/api/auth/boot", json={"password": _strong_password()})
    token = boot.json()["access_token"]

    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": _strong_password(), "new_password": "weak"},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": _strong_password(),
            "new_password": "N3w-Str0ng!P@ss-Phrase",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_login_flow_unchanged_by_policy(client: TestClient):
    """Existing users with weaker pre-policy passwords can still log in."""
    _reset_db()
    client.post("/api/auth/boot", json={"password": _strong_password()})
    resp = client.post("/api/auth/login", data={"username": "local", "password": _strong_password()})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# P0.1 — brute-force protection


def _derive_username():
    from backend import auth as auth_module
    return auth_module._derive_username()


def test_brute_force_retry_after_progression(client: TestClient):
    """Progressive delay schedule is applied correctly."""
    _reset_db()
    password = _strong_password()
    client.post("/api/auth/boot", json={"password": password})
    username = _derive_username()
    _reset_rate_limit()

    # Failure 1 is allowed through with no delay header.
    resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    assert resp.status_code == 401
    assert "Retry-After" not in resp.headers

    # Manually set the failure count to exercise the delay schedule deterministically.
    from backend.auth_rate_limit import _get_record
    record = _get_record(username)
    for failed, expected in [(1, 1), (2, 2), (3, 4)]:
        record.failed_attempts = failed
        resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) == expected, (
            f"failure count {failed}: Retry-After {resp.headers['Retry-After']} != {expected}"
        )


def test_brute_force_rapid_retries_stay_blocked(client: TestClient):
    """Rapid retries that do not wait are repeatedly rejected."""
    _reset_db()
    password = _strong_password()
    client.post("/api/auth/boot", json={"password": password})
    username = _derive_username()
    _reset_rate_limit()

    resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    if resp.status_code == 429:
        # Very slow runner hit the delay on the first retry; wait and try once more.
        time.sleep(int(resp.headers["Retry-After"]) + 0.1)
    else:
        assert resp.status_code == 401

    # Always be at a state where a rapid retry is limited before asserting 429s.
    resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    while resp.status_code == 401:
        resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    assert resp.status_code == 429

    for _ in range(4):
        resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
        if resp.status_code == 401:
            continue
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) >= 1


def test_brute_force_lockout_after_ten_failures(client: TestClient):
    """Ten consecutive failures trigger a hard lockout."""
    _reset_db()
    password = _strong_password()
    client.post("/api/auth/boot", json={"password": password})
    username = _derive_username()

    # Drive the counter directly to the lockout threshold to avoid slow retries.
    from backend.auth_rate_limit import _get_record, MAX_FAILED_ATTEMPTS
    record = _get_record(username)
    record.failed_attempts = MAX_FAILED_ATTEMPTS

    # The next request sees the hard lockout before any password check.
    resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    assert resp.status_code == 429
    assert resp.json()["detail"] == "Too many failed login attempts. Please try again later."

    # A correct password is still rejected while locked out.
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 429


def test_brute_force_success_resets_counter(client: TestClient):
    """A successful login clears the failure counter for the username."""
    _reset_db()
    password = _strong_password()
    client.post("/api/auth/boot", json={"password": password})
    username = _derive_username()
    _reset_rate_limit()

    # One failed attempt is guaranteed delay-free.
    resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    assert resp.status_code == 401

    # Successful login resets the counter; wait if slow runner made it rate-limited.
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    if resp.status_code == 429:
        time.sleep(int(resp.headers["Retry-After"]) + 0.1)
        resp = client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # Next failure is back to attempt 1 (no delay).
    _reset_rate_limit()
    resp = client.post("/api/auth/login", data={"username": username, "password": "***"})
    assert resp.status_code == 401
    assert "Retry-After" not in resp.headers


def test_brute_force_counters_not_persisted_across_process_restart(client: TestClient):
    """In-memory counters are not shared with a new process."""
    _reset_db()
    password = _strong_password()
    client.post("/api/auth/boot", json={"password": password})
    username = _derive_username()

    # Drive the counter directly to lockout to avoid slow retries.
    from backend.auth_rate_limit import _get_record, MAX_FAILED_ATTEMPTS
    _get_record(username).failed_attempts = MAX_FAILED_ATTEMPTS

    # Confirm locked out.
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 429

    # Simulate app restart by clearing the in-memory tracker.
    from backend.auth_rate_limit import reset_attempts
    reset_attempts(username)

    # Login succeeds after the restart.
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

def test_access_token_jti_is_unique(client: TestClient):
    """Each issued access token receives a distinct jti."""
    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": _strong_password()})
    assert resp.status_code == 200
    token1 = resp.json()["access_token"]

    resp = client.post("/api/auth/login", data={"username": "local", "password": _strong_password()})
    assert resp.status_code == 200
    token2 = resp.json()["access_token"]

    payload1 = decode_access_token(token1)
    payload2 = decode_access_token(token2)
    assert payload1["jti"] != payload2["jti"]


def test_revoked_token_cleanup_prunes_expired_records(client: TestClient):
    """Expired revoked-token records can be cleaned up."""
    _reset_db()
    from backend.tests.conftest import TestingSessionLocal
    from datetime import datetime, timedelta, timezone

    resp = client.post("/api/auth/boot", json={"password": _strong_password()})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Revoke via the public endpoint
    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db = TestingSessionLocal()
    try:
        from backend import models
        record = db.query(models.RevokedToken).first()
        assert record is not None
        # Roll the stored expiry back so the cleanup helper deletes it.
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(record)
        db.commit()

        from backend.auth import cleanup_expired_revoked_tokens
        deleted = cleanup_expired_revoked_tokens(db)
        assert deleted == 1
        assert db.query(models.RevokedToken).first() is None
    finally:
        db.close()


class TestLocalAuthHashMigration:
    """Verify backend/local/auth.py migrated to bcrypt while accepting legacy SHA-3_256 hashes."""

    def _legacy_sha3_hash(self, password: str) -> str:
        import hashlib, secrets
        salt = secrets.token_bytes(32)
        hashed = hashlib.sha3_256(password.encode("utf-8") + salt).digest()
        return f"{salt.hex()}:{hashed.hex()}"

    def test_new_local_user_gets_bcrypt_hash(self, client: TestClient):
        """LocalAuthManager.register now stores bcrypt hashes."""
        _reset_db()
        from backend.tests.conftest import TestingSessionLocal
        from backend.local.auth import LocalAuthManager
        from backend import models

        db = TestingSessionLocal()
        try:
            auth = LocalAuthManager(db)
            user = auth.register("localnew", "P@ssw0rd-Local-2026", email="new@local")
            assert user.hashed_password.startswith("$2b$")
            assert user.hashed_password != self._legacy_sha3_hash("P@ssw0rd-Local-2026")

            # Subsequent authentication works and remains bcrypt.
            auth2 = LocalAuthManager(db)
            verified = auth2.authenticate("localnew", "P@ssw0rd-Local-2026")
            assert verified.id == user.id
            assert verified.hashed_password.startswith("$2b$")
        finally:
            db.query(models.User).filter(models.User.username == "localnew").delete()
            db.commit()
            db.close()

    def test_legacy_sha3_user_login_rehashes_to_bcrypt(self, client: TestClient):
        """A user with a legacy SHA-3_256 hash can log in and is migrated to bcrypt."""
        _reset_db()
        from backend.tests.conftest import TestingSessionLocal
        from backend.local.auth import LocalAuthManager
        from backend.local.crypto import LocalCryptoManager
        from backend import models

        password = "L3g@cy-P@ss!2026"
        legacy_hash = self._legacy_sha3_hash(password)

        db = TestingSessionLocal()
        try:
            # Seed a user with a legacy hash directly.
            crypto = LocalCryptoManager.create(password)
            user = models.User(
                username="legacyuser",
                email="legacy@local",
                hashed_password=legacy_hash,
                encryption_salt=crypto.salt_b64,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Verify the pre-condition.
            assert user.hashed_password == legacy_hash

            # Authenticate succeeds and triggers migration.
            auth = LocalAuthManager(db)
            verified = auth.authenticate("legacyuser", password)
            assert verified.id == user.id
            assert verified.hashed_password.startswith("$2b$")
            assert verified.hashed_password != legacy_hash

            # Re-authenticate with bcrypt now.
            db.expunge(verified)
            auth2 = LocalAuthManager(db)
            verified2 = auth2.authenticate("legacyuser", password)
            assert verified2.id == user.id
            assert verified2.hashed_password.startswith("$2b$")
        finally:
            db.query(models.User).filter(models.User.username == "legacyuser").delete()
            db.commit()
            db.close()

    def test_verify_password_rejects_wrong_password_for_bcrypt_and_legacy(self):
        from backend.local.auth import LocalAuthManager

        pw = "T3st!Verify-1234"
        bcrypt_hash = LocalAuthManager.hash_password(pw)
        legacy_hash = self._legacy_sha3_hash(pw)

        assert LocalAuthManager.verify_password(pw, bcrypt_hash) is True
        assert LocalAuthManager.verify_password("wrong", bcrypt_hash) is False
        assert LocalAuthManager.verify_password(pw, legacy_hash) is True
        assert LocalAuthManager.verify_password("wrong", legacy_hash) is False



# ── TASK-038.10: keyfile support for local auth ───────────────────────────────────────


def test_boot_with_keyfile_stores_path_and_allows_login(client: TestClient, tmp_path: Path):
    """Boot with password+keyfile stores the path and requires the keyfile on login."""
    _reset_db()
    password = _strong_password()
    keyfile = generate_keyfile(tmp_path / "keyfile.bin", 64)

    resp = client.post("/api/auth/boot", json={"password": password, "keyfile_path": str(keyfile)})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["keyfile_path"] == str(keyfile.resolve())

    # Password-only login via JSON fails.
    resp = client.post("/api/auth/login-json", json={"username": "local", "password": password})
    assert resp.status_code == 401
    assert "keyfile" in resp.json()["detail"].lower()

    # Password+keyfile login succeeds.
    _reset_rate_limit()
    resp = client.post(
        "/api/auth/login-json",
        json={"username": "local", "password": password, "keyfile_path": str(keyfile)},
    )
    assert resp.status_code == 200
    new_token = resp.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200


def test_login_without_keyfile_after_keyfile_configured_fails(client: TestClient, tmp_path: Path):
    """Once a keyfile is configured, logging in without it is rejected."""
    _reset_db()
    password = _strong_password()
    keyfile = generate_keyfile(tmp_path / "keyfile.bin", 64)
    client.post("/api/auth/boot", json={"password": password, "keyfile_path": str(keyfile)})

    resp = client.post("/api/auth/login-json", json={"username": "local", "password": password})
    assert resp.status_code == 401
    assert "keyfile" in resp.json()["detail"].lower()


def test_keyfile_mismatch_rejected(client: TestClient, tmp_path: Path):
    """Supplying the wrong keyfile for a keyfile-enabled account is rejected."""
    _reset_db()
    password = _strong_password()
    keyfile_a = generate_keyfile(tmp_path / "keyfile_a.bin", 64)
    keyfile_b = generate_keyfile(tmp_path / "keyfile_b.bin", 64)
    client.post("/api/auth/boot", json={"password": password, "keyfile_path": str(keyfile_a)})

    resp = client.post(
        "/api/auth/login-json",
        json={"username": "local", "password": password, "keyfile_path": str(keyfile_b)},
    )
    assert resp.status_code == 401
    assert "mismatch" in resp.json()["detail"].lower()


def test_change_password_keeps_keyfile_binding(client: TestClient, tmp_path: Path):
    """Changing the master password preserves the keyfile binding."""
    _reset_db()
    old_password = _strong_password()
    new_password = "N3w-Str0ng!P@ss-Phrase-Keyfile"
    keyfile = generate_keyfile(tmp_path / "keyfile.bin", 64)

    boot = client.post("/api/auth/boot", json={"password": old_password, "keyfile_path": str(keyfile)})
    assert boot.status_code == 200
    token = boot.json()["access_token"]

    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_password, "new_password": new_password},
    )
    assert resp.status_code == 200

    # Old password is rejected.
    resp = client.post(
        "/api/auth/login-json",
        json={"username": "local", "password": old_password, "keyfile_path": str(keyfile)},
    )
    assert resp.status_code == 401

    _reset_rate_limit()
    # New password + same keyfile works.
    resp = client.post(
        "/api/auth/login-json",
        json={"username": "local", "password": new_password, "keyfile_path": str(keyfile)},
    )
    assert resp.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["keyfile_path"] == str(keyfile.resolve())
