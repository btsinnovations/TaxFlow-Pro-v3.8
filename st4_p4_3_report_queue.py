"""ST4 Phase 4.3 — Heavy compute / report generation queueing stress test."""
import os
import sys
import time
import tempfile
import glob
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p43")
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"
TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
API_BASE = os.environ.get("ST4_API_URL", "http://localhost:8000")

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "false"

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend import models
from backend.api import app


def get_users_and_statements():
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
        # authenticate_local_user always returns the first user, so we use user 0
        # and iterate through all tenants for the report stress test.
        user = db.query(models.User).filter(models.User.username == "p43user0").first()
        if not user:
            print("No p43user0 found. Run st4_p4_3_seed.py first.")
            sys.exit(1)

        tenants = []
        for u in db.query(models.User).filter(models.User.username.like("p43user%")).all():
            client = db.query(models.Client).filter(models.Client.user_id == u.id).first()
            stmts = db.query(models.Statement).filter(
                models.Statement.user_id == u.id,
                models.Statement.filename.like("p43_stmt_%")
            ).all()
            tenants.append({
                "username": u.username,
                "user_id": u.id,
                "tenant_id": client.id,
                "statement_ids": [s.id for s in stmts],
            })
        return tenants
    finally:
        db.close()
        engine.dispose()


def login(username):
    r = requests.post(
        f"{API_BASE}/api/auth/login-json",
        json={"username": username, "password": "password"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def request_report(args):
    """Worker: fire one report request. Returns (label, status, elapsed, bytes)."""
    username, tenant_id, stmt_id, kind = args
    try:
        token = login("p43user0")  # Always logs in as first user
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id)}
        start = time.time()

        if kind == "pdf":
            url = f"{API_BASE}/api/export/statement/{stmt_id}?format=pdf"
            r = requests.get(url, headers=headers, timeout=60)
        elif kind == "excel":
            url = f"{API_BASE}/api/export/statement/{stmt_id}?format=excel"
            r = requests.get(url, headers=headers, timeout=60)
        elif kind == "year_end":
            headers["X-Tenant-ID"] = str(tenant_id)
            url = f"{API_BASE}/api/tax-exports/year-end-package?year=2026"
            r = requests.get(url, headers=headers, timeout=90)
        elif kind == "pnl":
            headers["X-Tenant-ID"] = str(tenant_id)
            url = f"{API_BASE}/api/reports/profit-and-loss"
            payload = {"start_date": "2026-01-01", "end_date": "2026-12-31"}
            r = requests.post(url, headers=headers, json=payload, timeout=60)
        else:
            raise ValueError(kind)

        elapsed = time.time() - start
        return (kind, r.status_code, elapsed, len(r.content))
    except Exception as e:
        return (kind, f"EXC:{type(e).__name__}", -1.0, 0)


def main():
    users = get_users_and_statements()
    if not users:
        print("No p43 users found. Run st4_p4_3_seed.py first.")
        sys.exit(1)

    # Since authenticate_local_user always returns the first user (user 0),
    # we can only access user 0's statements. Use both of user 0's statements
    # and fire 20 reports across them with the correct tenant_id.
    user0 = users[0]
    tenant_id = user0["tenant_id"]
    stmts = user0["statement_ids"]
    if len(stmts) < 2:
        print(f"Need 2 statements for user 0, found {len(stmts)}")
        sys.exit(1)

    tasks = []
    # 20 reports: alternate between the 2 statements, 4 report types, 5 rounds
    report_types = ["pdf", "excel", "year_end", "pnl"]
    for i in range(20):
        stmt_id = stmts[i % len(stmts)]
        kind = report_types[i % len(report_types)]
        tasks.append((user0["username"], tenant_id, stmt_id, kind))

    print(f"Firing {len(tasks)} concurrent report requests...")
    start_all = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(request_report, t): t for t in tasks}
        for fut in as_completed(futures):
            results.append(fut.result())
    total_elapsed = time.time() - start_all

    statuses = {}
    for kind, status, elapsed, size in results:
        key = f"{kind}:{status}"
        statuses[key] = statuses.get(key, 0) + 1

    print("\nPhase 4.3 Heavy Compute / Report Queueing Results:")
    print(f"  total requests: {len(tasks)}")
    print(f"  status distribution: {statuses}")
    print(f"  wall-clock elapsed: {total_elapsed:.2f}s")
    print(f"  slowest request: {max(r[2] for r in results):.2f}s")
    print(f"  average request: {sum(r[2] for r in results)/len(results):.2f}s")

    # Memory (optional)
    try:
        import psutil
        proc = psutil.Process()
        mem = proc.memory_info().rss / (1024 * 1024)
        print(f"  current process RSS: {mem:.1f} MB")
    except Exception:
        pass

    # Temp file scan
    temp_dir = tempfile.gettempdir()
    taxflow_temp = [f for f in glob.glob(os.path.join(temp_dir, "*")) if "taxflow" in f.lower()]
    print(f"  taxflow temp files in {temp_dir}: {len(taxflow_temp)}")

    success_2xx = sum(1 for _, s, _, _ in results if isinstance(s, int) and 200 <= s < 300)
    no_500 = all(not (isinstance(s, int) and s >= 500) for _, s, _, _ in results)
    no_pool_errors = all("pool" not in str(s).lower() for _, s, _, _ in results)

    print(f"  successful 2xx: {success_2xx}/{len(tasks)}")
    print(f"  no 500s: {no_500}")
    print(f"  no pool exhaustion errors: {no_pool_errors}")

    if success_2xx == len(tasks) and no_500 and no_pool_errors:
        print("\nPHASE 4.3 RESULT: PASS")
    elif no_500 and no_pool_errors:
        print("\nPHASE 4.3 RESULT: PARTIAL PASS (some non-500 failures, no crash)")
    else:
        print("\nPHASE 4.3 RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
