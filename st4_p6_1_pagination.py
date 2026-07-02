"""ST4 Phase 6.1 — Pagination & cursor exhaustion stress test."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p61")
TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
API_BASE = os.environ.get("ST4_API_URL", "http://127.0.0.1:8000")

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "false"

import requests


def login():
    r = requests.post(
        f"{API_BASE}/api/auth/login-json",
        json={"username": "p61user", "password": "password"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main():
    token = login()
    # Query the DB to get the real tenant_id (client.id)
    from sqlalchemy import create_engine, text
    e = create_engine(f"postgresql://postgres@localhost:5433/{TEST_DB}")
    with e.connect() as c:
        tenant_id = c.execute(text("SELECT id FROM clients LIMIT 1")).scalar()
    e.dispose()
    if not tenant_id:
        print("FAIL: no tenant found in DB")
        sys.exit(1)
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id)}

    LIMIT = 50
    pages = [1, 100, 1000, 10000]
    results = []
    for page in pages:
        offset = (page - 1) * LIMIT
        url = f"{API_BASE}/api/transactions/?limit={LIMIT}&offset={offset}"
        start = time.time()
        r = requests.get(url, headers=headers, timeout=60)
        elapsed = time.time() - start
        count = len(r.json()) if r.status_code == 200 else 0
        results.append((page, r.status_code, elapsed, count))
        print(f"  page {page} (offset={offset}): {r.status_code} in {elapsed:.3f}s, {count} rows")

    # Past-end cursor
    offset = 999 * LIMIT
    url = f"{API_BASE}/api/transactions/?limit={LIMIT}&offset={offset}"
    start = time.time()
    r = requests.get(url, headers=headers, timeout=60)
    elapsed = time.time() - start
    count = len(r.json()) if r.status_code == 200 else 0
    print(f"  past-end (offset={offset}): {r.status_code} in {elapsed:.3f}s, {count} rows")

    slow = any(elapsed > 0.050 for _, _, elapsed, _ in results)
    if not slow:
        print("\nPHASE 6.1 RESULT: PASS (deep pages <50ms)")
    else:
        print("\nPHASE 6.1 RESULT: FAIL (slow deep pagination)")
        sys.exit(1)


if __name__ == "__main__":
    main()
