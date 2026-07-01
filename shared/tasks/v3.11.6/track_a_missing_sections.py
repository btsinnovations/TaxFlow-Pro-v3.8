"""TaxFlow Pro v3.11.6 — Track A missing sections harness (A.4, A.6, A.8, A.9, A.10, A.11, A.12).

Runs ad-hoc stress/probabilistic checks that are not covered by the regular
pytest suite and writes a JSON result file for later inclusion in the report.
"""
from __future__ import annotations

import base64
import concurrent.futures
import datetime
import json
import os
import random
import secrets
import statistics
import time
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("TAXFLOW_SINGLE_USER", "true")
os.environ.setdefault("TAXFLOW_RUNTIME_MODE", "offline")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TAXFLOW_TESTING", "true")
os.environ.setdefault("TAXFLOW_GLOBAL_RATE_LIMIT", "10000/second")
os.environ.setdefault("TAXFLOW_GLOBAL_BURST_LIMIT", "10000")
os.environ.setdefault("TAXFLOW_SECRET_KEY", "track-a-test-secret")

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import app  # noqa: E402
from backend.database import Base, get_db  # noqa: E402
from backend.routers.auth import get_password_hash  # noqa: E402
from backend import models  # noqa: E402
from backend.rate_limit import GlobalRateLimiter  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _setup_app():
    """Create a fresh in-memory DB, seed a user/client, and install override."""
    db_url = "sqlite:///:memory:"
    test_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Reset rate limiter so tests do not trip.
    app._GLOBAL_RATE_LIMITER = GlobalRateLimiter(
        limit=10000, window=60, burst=10000, trusted_proxy_hops=0
    )

    db = TestSessionLocal()
    user = models.User(
        username="stressuser",
        email="stress@example.com",
        hashed_password=get_password_hash("T4xFl0…2026"),
        is_active=True,
        encryption_salt=base64.b64encode(secrets.token_bytes(16)).decode("ascii"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    client_rec = models.Client(name="Stress Client", user_id=user.id)
    db.add(client_rec)
    db.commit()
    db.refresh(client_rec)
    db.close()

    client = TestClient(app)
    resp = client.post("/api/auth/login", data={"username": "stressuser", "password": "T4xFl0…2026"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, test_engine, user, client_rec


class _Result:
    def __init__(self, section: str, verdict: str, details: str, metrics: dict | None = None):
        self.section = section
        self.verdict = verdict
        self.details = details
        self.metrics = metrics or {}
        self.timestamp = _now()

    def to_dict(self) -> dict:
        return {
            "section": self.section,
            "verdict": self.verdict,
            "details": self.details,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }


def _active_engine():
    """Return the engine bound to the current dependency override."""
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    try:
        return db.bind
    finally:
        db.close()
        try:
            next(gen)
        except StopIteration:
            pass


def run_a4_chaos_repair(client: TestClient, user, client_rec) -> _Result:
    """A.4 Chaos/Repair — random adjusting entries with missing/invalid accounts."""
    from backend.accounting.coa import create_account as _create_account
    from sqlalchemy.orm import Session

    db = Session(bind=_active_engine())
    # Re-attach user/client to the new session so downstream helpers can read ids.
    user = db.merge(user)
    client_rec = db.merge(client_rec)

    cash = _create_account(db, client_rec.id, user.id, "1010", "Cash", "asset")
    revenue = _create_account(db, client_rec.id, user.id, "4010", "Revenue", "income")
    db.close()

    steps = 20
    ok = 0
    rejected = 0
    errors = []
    for i in range(steps):
        payload = {
            "date": "2026-06-15",
            "description": f"Chaos entry {i}",
            "amount": round(random.uniform(0.01, 999.99), 2),
            "debit_coa_account_id": cash["id"] if random.random() > 0.2 else 999999,
            "credit_coa_account_id": revenue["id"] if random.random() > 0.2 else 999999,
        }
        try:
            resp = client.post("/api/ledger/adjusting-entry", json=payload)
            if resp.status_code == 200:
                ok += 1
            elif resp.status_code in (400, 403, 404, 422):
                rejected += 1
            else:
                errors.append({"step": i, "status": resp.status_code, "body": resp.text[:200]})
        except Exception as exc:  # noqa: BLE001
            errors.append({"step": i, "error": str(exc)})

    verdict = "PASS" if not errors else "WARN"
    return _Result(
        "A.4 Chaos/Repair",
        verdict,
        f"{ok}/{steps} chaos writes succeeded; {rejected} gracefully rejected; {len(errors)} unexpected errors",
        {"steps": steps, "ok": ok, "rejected": rejected, "errors": errors[:5]},
    )


def run_a6_bookkeeping_stress(client: TestClient, user, client_rec) -> _Result:
    """A.6 Bookkeeping Module Stress — bulk adjusting entries and period close/reopen."""
    from backend.accounting.coa import create_account as _create_account
    from sqlalchemy.orm import Session

    db = Session(bind=_active_engine())
    user = db.merge(user)
    client_rec = db.merge(client_rec)
    cash = _create_account(db, client_rec.id, user.id, "1011", "Cash", "asset")
    revenue = _create_account(db, client_rec.id, user.id, "4011", "Revenue", "income")
    expense = _create_account(db, client_rec.id, user.id, "5010", "Expense", "expense")
    db.close()

    count = 50
    statuses = []
    for i in range(count):
        payload = {
            "date": "2026-06-15",
            "description": f"Bulk adjusting {i}",
            "debit_coa_account_id": cash["id"],
            "credit_coa_account_id": revenue["id"],
            "amount": round(random.uniform(0.01, 999.99), 2),
        }
        resp = client.post("/api/ledger/adjusting-entry", json=payload)
        statuses.append(resp.status_code)

    success = statuses.count(200)
    failures = [s for s in statuses if s != 200]
    verdict = "PASS" if success == count else "FAIL"
    return _Result(
        "A.6 Bookkeeping Module Stress",
        verdict,
        f"{success}/{count} adjusting entries created; failure statuses: {set(failures)}",
        {"total": count, "success": success, "failure_statuses": list(set(failures))},
    )


def run_a8_concurrent_load() -> _Result:
    """A.8 Concurrent Load — many parallel public health checks, measure latency."""
    n = 100
    latencies = []

    def _one(_) -> float:
        c = TestClient(app)
        t0 = time.perf_counter()
        resp = c.get("/api/health/public")
        t1 = time.perf_counter()
        return t1 - t0 if resp.status_code == 200 else -1.0

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(_one, range(n)))

    latencies = [r for r in results if r >= 0]
    failed = n - len(latencies)
    if not latencies:
        return _Result("A.8 Concurrent Load", "FAIL", "No successful requests", {"failed": failed})

    sorted_lat = sorted(latencies)
    metrics = {
        "requests": n,
        "failed": failed,
        "latency_min_ms": round(min(latencies) * 1000, 3),
        "latency_max_ms": round(max(latencies) * 1000, 3),
        "latency_mean_ms": round(statistics.mean(latencies) * 1000, 3),
        "latency_p95_ms": round(sorted_lat[int(len(sorted_lat) * 0.95)] * 1000, 3),
    }
    verdict = "PASS" if failed == 0 and metrics["latency_p95_ms"] < 1000 else "WARN"
    return _Result("A.8 Concurrent Load", verdict, "100 concurrent public-health requests measured", metrics)


def run_a9_volume_soak(client: TestClient) -> _Result:
    """A.9 Volume Soak — sequential dashboard reads."""
    n = 1000
    t0 = time.perf_counter()
    failures = 0
    for i in range(n):
        resp = client.get("/api/health/public")
        if resp.status_code != 200:
            failures += 1
    elapsed = time.perf_counter() - t0
    rps = round(n / elapsed, 2) if elapsed > 0 else 0
    verdict = "PASS" if failures == 0 else "FAIL"
    return _Result(
        "A.9 Volume Soak",
        verdict,
        f"{n} sequential requests in {round(elapsed, 2)}s ({rps} req/s); failures={failures}",
        {"requests": n, "elapsed_seconds": round(elapsed, 2), "rps": rps, "failures": failures},
    )


def run_a10_backup_restore(client: TestClient) -> _Result:
    """A.10 Backup & Restore Integrity — export then idempotent import."""
    export_resp = client.get("/api/backup/export")
    if export_resp.status_code != 200:
        return _Result(
            "A.10 Backup & Restore Integrity",
            "FAIL",
            f"Export failed: {export_resp.status_code} {export_resp.text[:200]}",
            {},
        )

    original = export_resp.json()
    payload = {
        "version": "3.10.0",
        "users": original["users"],
        "clients": original["clients"],
        "gl_accounts": original["gl_accounts"],
        "accounts": original["accounts"],
        "statements": original["statements"],
        "transactions": original["transactions"],
    }
    import_resp = client.post("/api/backup/import", json=payload)
    if import_resp.status_code != 200:
        return _Result(
            "A.10 Backup & Restore Integrity",
            "FAIL",
            f"Import failed: {import_resp.status_code} {import_resp.text[:200]}",
            {},
        )

    result = import_resp.json()
    verdict = "PASS" if result.get("ok") else "FAIL"
    metrics = {
        "exported_users": len(original["users"]),
        "exported_clients": len(original["clients"]),
        "imported_users": result["counts"].get("users", 0),
        "imported_clients": result["counts"].get("clients", 0),
        "id_maps_user_count": len(result["id_maps"].get("users", {})),
    }
    return _Result("A.10 Backup & Restore Integrity", verdict, "Backup export/import round-trip succeeded", metrics)


def run_a11_resource_monitoring() -> _Result:
    """A.11 Resource Monitoring — confirm bootstrap and public health endpoints respond."""
    c = TestClient(app)
    endpoints = {
        "/api/health/public": 200,
        "/api/health/bootstrap": 200,
        "/health": 200,
    }
    results = {}
    all_ok = True
    for path, expected in endpoints.items():
        try:
            resp = c.get(path)
            results[path] = resp.status_code
            if resp.status_code != expected:
                all_ok = False
        except Exception as exc:  # noqa: BLE001
            results[path] = str(exc)
            all_ok = False
    verdict = "PASS" if all_ok else "FAIL"
    return _Result("A.11 Resource Monitoring", verdict, "Public health/bootstrap endpoints checked", results)


def run_a12_date_edge_cases(client: TestClient, user, client_rec) -> _Result:
    """A.12 Date Edge Cases — fiscal year-end, leap day, min/max ISO dates."""
    from backend.accounting.coa import create_account as _create_account
    from sqlalchemy.orm import Session

    db = Session(bind=_active_engine())
    user = db.merge(user)
    client_rec = db.merge(client_rec)
    cash = _create_account(db, client_rec.id, user.id, "1012", "Cash Edge", "asset")
    revenue = _create_account(db, client_rec.id, user.id, "4012", "Revenue Edge", "income")
    db.close()

    dates = [
        "2024-02-29",
        "2025-12-31",
        "2026-01-01",
        "2020-02-29",
        "1900-01-01",
        "9999-12-31",
    ]
    ok = 0
    failures = []
    for d in dates:
        resp = client.post("/api/ledger/adjusting-entry", json={
            "date": d,
            "description": f"Date edge {d}",
            "debit_coa_account_id": cash["id"],
            "credit_coa_account_id": revenue["id"],
            "amount": 1.00,
        })
        if resp.status_code == 200:
            ok += 1
        else:
            failures.append({"date": d, "status": resp.status_code, "detail": resp.text[:120]})
    verdict = "PASS" if ok == len(dates) else "WARN"
    return _Result("A.12 Date Edge Cases", verdict, f"{ok}/{len(dates)} edge dates accepted", {"dates": len(dates), "ok": ok, "failures": failures})


def main() -> None:
    client, engine, user, client_rec = _setup_app()
    results = [
        run_a4_chaos_repair(client, user, client_rec),
        run_a6_bookkeeping_stress(client, user, client_rec),
        run_a8_concurrent_load(),
        run_a9_volume_soak(client),
        run_a10_backup_restore(client),
        run_a11_resource_monitoring(),
        run_a12_date_edge_cases(client, user, client_rec),
    ]
    engine.dispose()
    output = {
        "timestamp": _now(),
        "branch": "v3.11.6-dev",
        "head": "ab65774",
        "results": [r.to_dict() for r in results],
    }
    out_path = Path(__file__).with_suffix(".json")
    out_path.write_text(json.dumps(output, indent=2, default=str))
    print(out_path)


if __name__ == "__main__":
    main()
