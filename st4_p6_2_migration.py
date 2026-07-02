"""ST4 Phase 6.2 — Schema migration under load."""
import os
import sys
import time
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import random

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p62")
TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"
API_BASE = os.environ.get("ST4_API_URL", "http://127.0.0.1:8000")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "true"

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager


def run_alembic(action, revision):
    """Run alembic command via Python subprocess with explicit URL override."""
    script = (
        "import os, sys\n"
        f"sys.path.insert(0, r'{PROJECT_ROOT}')\n"
        f"os.environ['DATABASE_URL'] = r'{TEST_URL}'\n"
        "from alembic.config import Config\n"
        "from alembic import command\n"
        f"cfg = Config(r'{PROJECT_ROOT}\\alembic.ini')\n"
        f"cfg.set_main_option('sqlalchemy.url', r'{TEST_URL}')\n"
        f"command.{action}(cfg, '{revision}')\n"
        f"print('{action} {revision} done')\n"
    )
    env = dict(os.environ, DATABASE_URL=TEST_URL)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=300,
        cwd=PROJECT_ROOT, env=env,
    )
    return result


def seed_62():
    """Seed the p62 DB with a user, tenant, account, statement, and 100K transactions."""
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
        db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

        user = db.query(models.User).filter(models.User.username == "p62user").first()
        if user is None:
            crypto = LocalCryptoManager.create("password")
            user = models.User(
                username="p62user",
                email="p62@example.com",
                hashed_password=get_password_hash("password"),
                encryption_salt=crypto.salt_b64,
                is_active=True,
            )
            db.add(user); db.commit(); db.refresh(user)

        client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
        if client is None:
            client = models.Client(name="P62 Tenant", user_id=user.id)
            db.add(client); db.commit(); db.refresh(client)

        account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
        if account is None:
            account = models.Account(
                name="Checking", type="checking",
                client_id=client.id, tenant_id=client.id, user_id=user.id,
            )
            db.add(account); db.commit(); db.refresh(account)

        statement = db.query(models.Statement).filter(models.Statement.user_id == user.id).first()
        if statement is None:
            statement = models.Statement(
                user_id=user.id, tenant_id=client.id, account_id=account.id,
                filename="p62_seed.csv",
                period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
                opening_balance=0.0, closing_balance=0.0, variance=0.0, is_balanced=False,
            )
            db.add(statement); db.commit(); db.refresh(statement)

        target = 100_000
        existing = db.query(models.Transaction).filter(
            models.Transaction.tenant_id == client.id
        ).count()
        if existing < target:
            print(f"  Seeding {target - existing} transactions...")
            base = date(2026, 1, 1)
            batch = []
            for i in range(target - existing):
                batch.append(models.Transaction(
                    statement_id=statement.id,
                    tenant_id=client.id, user_id=user.id,
                    date=base + timedelta(days=i % 365),
                    description=f"Migration stress txn {existing + i + 1}",
                    amount=round(random.uniform(1.0, 1000.0), 2),
                    tx_type="debit", category="uncategorized",
                ))
                if len(batch) >= 5000:
                    db.bulk_save_objects(batch); db.commit(); batch = []
            if batch:
                db.bulk_save_objects(batch); db.commit()

        print(f"  Seeded: tenant_id={client.id}, txns={db.query(models.Transaction).filter(models.Transaction.tenant_id == client.id).count()}")
        return client.id
    finally:
        db.close()
        engine.dispose()


def background_load(token, tenant_id, stop_event):
    """Keep firing reads and writes while migration runs."""
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_id)}
    reads = 0
    writes = 0
    write_failures = 0
    while not stop_event.is_set():
        try:
            r = requests.get(f"{API_BASE}/api/transactions/?limit=10&offset=0",
                             headers=headers, timeout=10)
            if r.status_code == 200:
                reads += 1
        except Exception:
            pass
        try:
            payload = {
                "account_id": 1,
                "date": "2026-07-01",
                "description": "migration stress write",
                "amount": 1.0,
                "tx_type": "debit",
                "category": "uncategorized",
            }
            r = requests.post(f"{API_BASE}/api/transactions/",
                              headers=headers, json=payload, timeout=10)
            if r.status_code in (200, 201):
                writes += 1
            else:
                write_failures += 1
        except Exception:
            write_failures += 1
        time.sleep(0.1)
    return reads, writes, write_failures


def main():
    print("=" * 70)
    print("ST4 Phase 6.2 — Schema Migration Under Load")
    print(f"  DB: {TEST_DB}")
    print(f"  API: {API_BASE}")
    print("=" * 70)

    # Step 1: Seed data
    print("\n  Step 1: Seeding 100K transactions...")
    tenant_id = seed_62()

    # Step 2: Stamp DB to earlier revision
    print("\n  Step 2: Stamping DB to earlier revision (e8f4a2c1d0b5)...")
    # Stamp to f1a2b3c4d5e6 (after COA tables, before RLS/B3/R1-R5 migrations)
    # This leaves 8 real migrations to run during the load test, all of which
    # add new tables/columns rather than duplicating existing ones.
    result = run_alembic("stamp", "f1a2b3c4d5e6")
    print(f"    stamp stdout: {result.stdout.strip()}")
    if result.returncode != 0:
        print(f"    stamp stderr: {result.stderr.strip()[-300:]}")

    # Step 3: Login
    print("\n  Step 3: Logging in...")
    r = requests.post(
        f"{API_BASE}/api/auth/login-json",
        json={"username": "p62user", "password": "password"},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"    Login failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    token = r.json()["access_token"]
    print(f"    Logged in, token len {len(token)}")

    # Step 4: Background load + migration
    print("\n  Step 4: Starting background load + running alembic upgrade head...")
    stop_event = threading.Event()

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(background_load, token, tenant_id, stop_event) for _ in range(5)]

        start = time.time()
        result = run_alembic("upgrade", "head")
        elapsed = time.time() - start
        stop_event.set()

    print(f"  alembic returncode: {result.returncode}")
    print(f"  alembic stdout: {result.stdout.strip()[-500:]}")
    if result.stderr.strip():
        print(f"  alembic stderr: {result.stderr.strip()[-500:]}")
    print(f"  migration elapsed: {elapsed:.2f}s")

    totals = {"reads": 0, "writes": 0, "write_failures": 0}
    for fut in futures:
        reads, writes, write_failures = fut.result()
        totals["reads"] += reads
        totals["writes"] += writes
        totals["write_failures"] += write_failures

    print(f"  background reads: {totals['reads']}")
    print(f"  background writes: {totals['writes']}")
    print(f"  background write failures: {totals['write_failures']}")

    # Verdict
    print("\n" + "=" * 70)
    print("PHASE 6.2 VERDICT")
    print("=" * 70)

    passed = True
    failures = []

    if result.returncode != 0:
        failures.append("Alembic migration failed")
        passed = False
    else:
        print("  [PASS] Migration completed successfully")

    if totals["reads"] == 0:
        failures.append("No background reads completed")
        passed = False
    else:
        print(f"  [PASS] Background reads survived: {totals['reads']}")

    if totals["reads"] > 0 and totals["write_failures"] > totals["writes"] * 10:
        failures.append(f"Excessive write failures: {totals['write_failures']} vs {totals['writes']}")
        passed = False
    else:
        print(f"  [PASS] Write handling graceful: {totals['writes']} ok, {totals['write_failures']} failed")

    if passed:
        print(f"\n  PHASE 6.2 RESULT: PASS")
    else:
        print(f"\n  PHASE 6.2 RESULT: FAIL")
        for f in failures:
            print(f"    - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()