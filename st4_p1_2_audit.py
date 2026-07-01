"""Stress Test 4 Phase 1.2 — Audit Trail Immutability Under Load."""
import os
import sys
import time
import random
import threading
import concurrent.futures

TEST_DB = os.environ.get("ST4_TEST_DB")
if not TEST_DB:
    print("Set ST4_TEST_DB env var")
    sys.exit(1)

TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "false"

from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager


def seed_user_and_account(db, username, user_num):
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        crypto = LocalCryptoManager.create("password")
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            hashed_password=get_password_hash("password"),
            encryption_salt=crypto.salt_b64,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.encryption_salt:
        crypto = LocalCryptoManager.create("password")
        user.encryption_salt = crypto.salt_b64
        db.add(user)
        db.commit()
        db.refresh(user)

    client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
    if client is None:
        client = models.Client(name=f"Audit Client {user_num}", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

    account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
    if account is None:
        account = models.Account(name="Checking", type="checking", client_id=client.id, tenant_id=client.id, user_id=user.id)
        db.add(account)
        db.commit()
        db.refresh(account)

    coa = db.query(models.CoaAccount).filter(models.CoaAccount.tenant_id == client.id, models.CoaAccount.number == 1010).first()
    if coa is None:
        coa = models.CoaAccount(tenant_id=client.id, number=1010, name="Cash", type="asset")
        db.add(coa)
        db.commit()
        db.refresh(coa)

    return user, client, account, coa


def login_client(tenant_id, username):
    c = TestClient(app)
    c.headers["X-Tenant-ID"] = str(tenant_id)
    r = c.post("/api/auth/login", data={"username": username, "password": "password"})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {username}: {r.status_code} {r.text}")
    token = r.json()["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return c


def worker(username, tenant_id, account_id, coa_id, results, stop_flag):
    try:
        c = login_client(tenant_id, username)
    except Exception as e:
        results[username] = {"created": 0, "read_attempts": 0, "write_attempts": 0, "forbidden": 0, "error": str(e)}
        return
    created = 0
    read_attempts = 0
    write_attempts = 0
    blocked = 0
    errors = 0
    while not stop_flag.is_set():
        action = random.choice(["create", "create", "read", "tamper_delete", "tamper_put"])
        try:
            if action == "create":
                payload = {
                    "account_id": account_id,
                    "date": date(2026, 7, 1).isoformat(),
                    "description": f"txn by {username} {time.time()}",
                    "amount": round(random.uniform(1, 100), 2),
                    "tx_type": "debit",
                    "category": "uncategorized",
                    "coa_account_id": coa_id,
                }
                r = c.post("/api/transactions", json=payload)
                if r.status_code == 201:
                    created += 1
                write_attempts += 1
            elif action == "read":
                r = c.get("/api/audit/logs")
                read_attempts += 1
            elif action == "tamper_delete":
                r = c.delete("/api/audit/logs")
                if r.status_code not in (200, 201, 204):
                    blocked += 1
                write_attempts += 1
            else:
                r = c.put("/api/audit/logs", json={})
                if r.status_code not in (200, 201):
                    blocked += 1
                write_attempts += 1
        except Exception:
            errors += 1
    results[username] = {"created": created, "read_attempts": read_attempts, "write_attempts": write_attempts, "blocked": blocked, "errors": errors}


def main():
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    users = []
    for i in range(20):
        username = f"audit{i}"
        user, client, account, coa = seed_user_and_account(db, username, i)
        users.append((username, client.id, account.id, coa.id))
    db.close()
    engine.dispose()

    stop_flag = threading.Event()
    results = {}
    threads = []
    for username, tenant_id, account_id, coa_id in users:
        t = threading.Thread(target=worker, args=(username, tenant_id, account_id, coa_id, results, stop_flag))
        t.start()
        threads.append(t)

    time.sleep(30)
    stop_flag.set()
    for t in threads:
        t.join()

    admin_engine = create_engine(ADMIN_URL)
    adb = sessionmaker(bind=admin_engine)()
    adb.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    adb.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))
    total_audit = adb.query(models.AuditEntry).count()
    tampered = False
    for row in adb.execute(text("SELECT action FROM audit_entries")).fetchall():
        if row[0] in ("DELETE", "UPDATE"):
            tampered = True
            break
    adb.close()
    admin_engine.dispose()

    print("\nPhase 1.2 Audit Trail Immutability Results:")
    total_created = sum(r.get("created", 0) for r in results.values())
    total_reads = sum(r.get("read_attempts", 0) for r in results.values())
    total_writes = sum(r.get("write_attempts", 0) for r in results.values())
    total_blocked = sum(r.get("blocked", 0) for r in results.values())
    total_errors = sum(r.get("errors", 0) for r in results.values())
    print(f"  transactions created: {total_created}")
    print(f"  audit reads: {total_reads}")
    print(f"  tamper write attempts: {total_writes}")
    print(f"  tamper attempts blocked: {total_blocked}/{total_writes}")
    print(f"  thread errors: {total_errors}")
    print(f"  audit entries stored: {total_audit}")
    print(f"  audit tampered: {tampered}")

    if total_writes > 0 and not tampered:
        print("\nPHASE 1.2 RESULT: PASS")
    else:
        print("\nPHASE 1.2 RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
