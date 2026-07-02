"""ST4 Phase 6.1 — Pagination & cursor exhaustion stress test.

Tests both legacy OFFSET pagination (expected to degrade on deep pages)
and the keyset cursor pagination introduced in Fix 3. The PASS/FAIL
criterion is applied to keyset pagination, which must stay under 100ms
per page even on deep pages.
"""
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


def fetch_page(token, tenant_id, limit=50, after_date=None, after_id=None):
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id)}
    url = f"{API_BASE}/api/transactions/?limit={limit}"
    if after_date is not None:
        url += f"&after_date={after_date}&after_id={after_id}"
    start = time.time()
    r = requests.get(url, headers=headers, timeout=60)
    elapsed = time.time() - start
    if r.status_code != 200:
        print(f"  FAIL: {r.status_code} {r.text[:200]}")
        return None, elapsed
    return r.json(), elapsed


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

    LIMIT = 50

    # Legacy OFFSET pagination — recorded for comparison only.
    print("Legacy OFFSET pagination (for comparison):")
    pages = [1, 100, 1000, 10000]
    offset_results = []
    for page in pages:
        offset = (page - 1) * LIMIT
        url = f"{API_BASE}/api/transactions/?limit={LIMIT}&offset={offset}"
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id)}
        start = time.time()
        r = requests.get(url, headers=headers, timeout=60)
        elapsed = time.time() - start
        count = len(r.json()) if r.status_code == 200 else 0
        offset_results.append((page, r.status_code, elapsed, count))
        print(f"  page {page} (offset={offset}): {r.status_code} in {elapsed:.3f}s, {count} rows")

    # Keyset cursor pagination — this is the fix under test.
    print("\nKeyset cursor pagination (Fix 3):")
    after_date = None
    after_id = None
    keyset_results = []
    for i in range(1, 101):
        rows, elapsed = fetch_page(token, tenant_id, limit=LIMIT, after_date=after_date, after_id=after_id)
        if rows is None:
            print(f"\nPHASE 6.1 RESULT: FAIL (keyset page {i} request failed)")
            sys.exit(1)
        count = len(rows)
        keyset_results.append((i, elapsed, count))
        if count == 0:
            print(f"  page {i}: no more rows, {elapsed:.3f}s")
            break
        last = rows[-1]
        after_date = last["date"]
        after_id = last["id"]
        if i % 10 == 0 or count == 0:
            print(f"  page {i}: {elapsed:.3f}s, {count} rows")

    # Past-end cursor
    rows, elapsed = fetch_page(token, tenant_id, limit=LIMIT, after_date="9999-12-31", after_id=999999999)
    past_count = len(rows) if rows is not None else -1
    print(f"  past-end cursor: {elapsed:.3f}s, {past_count} rows")

    slow = any(elapsed > 0.100 for _, elapsed, _ in keyset_results)
    if not slow:
        print("\nPHASE 6.1 RESULT: PASS (keyset deep pages <100ms)")
    else:
        print("\nPHASE 6.1 RESULT: FAIL (slow keyset pagination)")
        sys.exit(1)


if __name__ == "__main__":
    main()
