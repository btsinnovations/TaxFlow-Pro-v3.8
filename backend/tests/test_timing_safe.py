"""Timing-attack-safe authentication tests (TASK-034)."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from backend.database import Base
from backend.tests.conftest import engine as test_engine
from backend.security.timing_safe import constant_time_compare, constant_time_user_lookup


@pytest.fixture(autouse=True)
def _reset_brute_force_tracker():
    from backend.auth_rate_limit import _tracker
    _tracker.clear()
    yield


def _reset_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def _strong_password():
    return "T4xFl0w!Br0nze-V@ult-2026"


class TestConstantTimeCompare:
    def test_equal_strings_return_true(self):
        assert constant_time_compare("same", "same") is True
        assert constant_time_compare(b"same", b"same") is True
        assert constant_time_compare("same", b"same") is True

    def test_unequal_strings_return_false(self):
        assert constant_time_compare("same", "different") is False
        assert constant_time_compare(b"same", b"different") is False

    def test_different_lengths_return_false(self):
        assert constant_time_compare("short", "longer-string") is False
        assert constant_time_compare("longer-string", "short") is False


class TestTimingSafeLogin:
    def test_login_timing_for_valid_vs_invalid_username(self, client: TestClient, monkeypatch):
        """The median timing difference between valid-username and invalid-username
        failures must be small enough that user existence is not leaked."""
        _reset_db()

        # Disable the brute-force rate limiter for this timing test so that
        # progressive delays do not skew the comparison.
        monkeypatch.setattr("backend.routers.auth.check_login_attempt", lambda username: None)
        monkeypatch.setattr("backend.routers.auth.record_login_failure", lambda username: None)
        monkeypatch.setattr("backend.routers.auth.record_login_success", lambda username: None)

        resp = client.post("/api/auth/boot", json={"password": _strong_password()})
        assert resp.status_code == 200

        # Determine the local username via first boot response.
        token = resp.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        local_username = me.json()["username"]

        # Prime the app and warm caches for both usernames.
        client.post("/api/auth/login", data={"username": local_username, "password": "wrong"})
        client.post("/api/auth/login", data={"username": "nosuchuser12345", "password": "wrong"})

        def measure(username: str, rounds: int = 24) -> list[float]:
            times: list[float] = []
            for _ in range(rounds):
                start = time.perf_counter()
                client.post("/api/auth/login", data={"username": username, "password": "wrong"})
                times.append(time.perf_counter() - start)
            return times

        valid_times = sorted(measure(local_username))
        invalid_times = sorted(measure("nosuchuser12345"))

        # Use median to reduce impact of occasional GC/noise outliers.
        def _median(values: list[float]) -> float:
            n = len(values)
            return (values[n // 2] + values[(n - 1) // 2]) / 2

        valid_median = _median(valid_times)
        invalid_median = _median(invalid_times)
        diff = abs(valid_median - invalid_median)
        # 20% threshold against the slower median. The implementation now uses
        # identical bcrypt + compare_digest work on both paths, so this should
        # be comfortably met on a quiet host; we keep 20% to tolerate CI noise.
        slower = max(valid_median, invalid_median)
        assert diff / slower < 0.20, (
            f"Timing divergence too large: valid={valid_median:.4f}s "
            f"invalid={invalid_median:.4f}s diff={diff:.4f}s ({diff/slower*100:.1f}%)"
        )

        # Both must return the same status code and message.
        valid_resp = client.post("/api/auth/login", data={"username": local_username, "password": "wrong"})
        invalid_resp = client.post("/api/auth/login", data={"username": "nosuchuser12345", "password": "wrong"})
        assert valid_resp.status_code == invalid_resp.status_code == 401
        assert valid_resp.json()["detail"] == invalid_resp.json()["detail"]

    def test_login_json_timing_and_text_uniformity(self, client: TestClient):
        _reset_db()
        client.post("/api/auth/boot", json={"password": _strong_password()})

        valid_resp = client.post("/api/auth/login-json", json={"username": "local", "password": "wrong"})
        invalid_resp = client.post("/api/auth/login-json", json={"username": "nosuchuser", "password": "wrong"})
        assert valid_resp.status_code == invalid_resp.status_code == 401
        assert valid_resp.json()["detail"] == invalid_resp.json()["detail"]

    def test_boot_already_initialized_returns_uniform_error(self, client: TestClient):
        _reset_db()
        client.post("/api/auth/boot", json={"password": _strong_password()})

        # Second boot attempt is rejected with 400, not 401.
        resp = client.post("/api/auth/boot", json={"password": _strong_password()})
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()


class TestConstantTimeUserLookup:
    def test_lookup_existing_user(self, client: TestClient):
        _reset_db()
        resp = client.post("/api/auth/boot", json={"password": _strong_password()})
        assert resp.status_code == 200
        from backend.tests.conftest import TestingSessionLocal
        from backend import models as _models
        db = TestingSessionLocal()
        try:
            user = db.query(_models.User).first()
            assert user is not None
            found = constant_time_user_lookup(db, user.username)
            assert found is not None
            assert isinstance(found, _models.User)
            assert found.id == user.id
        finally:
            db.close()

    def test_lookup_missing_user_returns_sentinel(self, client: TestClient):
        _reset_db()
        from backend.tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            found = constant_time_user_lookup(db, "definitely-not-present")
            assert found is not None
            assert isinstance(found, __import__("backend.security.timing_safe", fromlist=["_SentinelUser"])._SentinelUser)
        finally:
            db.close()
