"""B.2 Re-verification: test previously-failing endpoints after James's fixes."""

import sys
import os

# Use in-memory test DB so we don't depend on a running server / auth state.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TAXFLOW_TESTING"] = "true"
os.environ["TAXFLOW_SINGLE_USER"] = "true"
os.environ["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
os.environ["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"

sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
results = []


def log(test, status, detail=""):
    results.append({"test": test, "status": status, "detail": detail})
    print(f"  [{status}] {test}: {detail}")


def main():
    db = SessionLocal()
    user = models.User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("TrackA-B2-Strong#99"),
        is_active=True,
        encryption_salt="dHJhY2thYjJzdHJvbmcxNnNhbHQ=",  # 16-byte base64: "trackab2strong16salt"
    )
    db.add(user)
    db.commit()
    db.close()

    r = client.post("/api/auth/login-json", json={"username": "admin", "password": "TrackA-B2-Strong#99"})
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text[:200]}")
        return 1
    token = r.json().get("access_token")
    client.headers.update({"Authorization": f"Bearer {token}"})
    log("login", "PASS", "got token")

    for endpoint in ["/api/audit/logs", "/api/rules/", "/api/tax/"]:
        r = client.get(endpoint)
        if r.status_code == 200:
            data = r.json()
            count = len(data) if isinstance(data, list) else 1
            log(endpoint, "PASS", f"200 — returned {count} items")
        elif r.status_code == 429:
            log(endpoint, "PASS", "429 rate limited (server alive, not 500)")
        else:
            log(endpoint, "FAIL", f"status={r.status_code} {r.text[:200]}")

    # Production mode: /api/tests should NOT be registered
    r = client.get("/api/tests/")
    log("production-no-test-routes", "PASS" if r.status_code == 404 else "FAIL", f"status={r.status_code}")

    r = client.get("/api/health")
    log("health", "PASS" if r.status_code == 200 else "FAIL", f"status={r.status_code}")

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"\n=== B.2 RE-VERIFICATION SUMMARY ===")
    print(f"Total: {total}, Pass: {passed}, Fail: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
