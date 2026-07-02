"""Stress Test 4 Phase 2.3 - DB pool exhaustion / slow DB simulation."""
import os, sys, time, threading, requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import date
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager

TEST_DB = os.environ["ST4_TEST_DB"]
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"
BASE_URL = os.environ.get("ST4_BASE_URL", "http://127.0.0.1:8000")
PASS_ENV = os.environ.get("ST4_PASSWORD", "password")

def seed(db):
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))
    user = db.query(models.User).filter(models.User.username == "network").first()
    if user is None:
        crypto = LocalCryptoManager.create(PASS_ENV)
        user = models.User(
            username="network",
            email="network@example.com",
            hashed_password=get_password_hash(PASS_ENV),
            encryption_salt=crypto.salt_b64,
            is_active=True,
        )
        db.add(user); db.commit(); db.refresh(user)
    elif not user.encryption_salt:
        user.encryption_salt = LocalCryptoManager.create(PASS_ENV).salt_b64
        db.add(user); db.commit(); db.refresh(user)
    client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
    if client is None:
        client = models.Client(name="Network Client", user_id=user.id)
        db.add(client); db.commit(); db.refresh(client)
    account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
    if account is None:
        account = models.Account(name="Checking", type="checking",
            client_id=client.id, tenant_id=client.id, user_id=user.id)
        db.add(account); db.commit(); db.refresh(account)
    return user, client, account

def login():
    payload = {"username": "network", "password": PASS_ENV}
    r = requests.post(f"{BASE_URL}/api/auth/login-json", json=payload, timeout=30)
    if r.status_code != 200:
        print("login failed:", r.status_code, r.text[:400])
        raise Exception("login failed")
    return r.json()["access_token"]

engine = create_engine(ADMIN_URL)
Session = sessionmaker(bind=engine)
db = Session()
user, client, account = seed(db)
tenant_id = client.id
db.close(); engine.dispose()

e0 = create_engine(ADMIN_URL)
db0 = sessionmaker(bind=e0)()
db0.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
db0.execute(text(f"SELECT set_config('taxflow.tenant_id', '{tenant_id}', false)"))
baseline = db0.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id).count()
db0.close(); e0.dispose()

token = login()
stop_event = threading.Event()

def hold():
    e = create_engine(ADMIN_URL, pool_size=20, max_overflow=0)
    sessions = []
    for _ in range(20):
        s = sessionmaker(bind=e)()
        t = threading.Thread(target=lambda s=s: s.execute(text("SELECT pg_sleep(30)")))
        t.daemon = True; t.start(); sessions.append((s, t))
    stop_event.wait()
    for s, t in sessions:
        try:
            s.rollback(); s.close()
        except Exception:
            pass
    e.dispose()

holder = threading.Thread(target=hold); holder.start(); time.sleep(2)

total = 100; success = 0; failure = 0; first_failure = None
print(f"Baseline transactions: {baseline}")
print(f"Starting {total} POSTs while DB pool is exhausted...")

for i in range(total):
    try:
        r = requests.post(
            f"{BASE_URL}/api/transactions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "tenant_id": tenant_id,
                "account_id": account.id,
                "date": "2026-07-01",
                "description": "network stress test",
                "amount": 1.0,
                "tx_type": "debit",
                "category": "uncategorized",
            },
            timeout=10,
        )
        if r.status_code == 201:
            success += 1
        else:
            failure += 1
            if first_failure is None:
                first_failure = f"{r.status_code} {r.text[:200]}"
    except Exception as ex:
        failure += 1
        if first_failure is None:
            first_failure = str(ex)[:200]

stop_event.set(); holder.join(timeout=5)

e1 = create_engine(ADMIN_URL)
db1 = sessionmaker(bind=e1)()
db1.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
db1.execute(text(f"SELECT set_config('taxflow.tenant_id', '{tenant_id}', false)"))
final = db1.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id).count()
db1.close(); e1.dispose()

print(f"\nPhase 2.3 Network/Pool Exhaustion Results:")
print(f"  total attempts: {total}")
print(f"  successes: {success}")
print(f"  failures: {failure}")
print(f"  first failure: {first_failure}")
print(f"  baseline tx count: {baseline}")
print(f"  final tx count: {final}")
print(f"  expected final count: {baseline + success}")
print(f"  no partial commits: {final == baseline + success}")

if final == baseline + success:
    print("\nPHASE 2.3 RESULT: PASS")
else:
    print("\nPHASE 2.3 RESULT: FAIL")
    sys.exit(1)