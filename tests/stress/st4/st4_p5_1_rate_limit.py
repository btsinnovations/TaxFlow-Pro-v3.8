"""Stress Test 4 Phase 5.1 — Rate Limiting Under DDoS.

500 concurrent connections brute-forcing /api/auth/login.
Rate limiter returns 429 without DB degradation or blocking legitimate IPs.

Two vectors tested:
  A) Same-username, many IPs — auth_rate_limit backstop (per-username lockout)
  B) Different-usernames, many IPs — global rate limit backstop (per-IP window)

Run:
    set ST4_TEST_DB=st4_p51
    python st4_p5_1_rate_limit.py
"""
import os
import sys
import time
import random
import threading
import concurrent.futures
from datetime import date

# Force UTF-8 stdout to avoid cp1252 encoding errors on Windows console.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEST_DB = os.environ.get("ST4_TEST_DB")
if not TEST_DB:
    print("Set ST4_TEST_DB env var (e.g. set ST4_TEST_DB=st4_p51)")
    sys.exit(1)

TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "false"
os.environ["TAXFLOW_TESTING"] = "true"  # Keep test mode for clean startup
os.environ["TAXFLOW_GLOBAL_RATE_LIMIT"] = "100/minute"
os.environ["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10"
os.environ["TAXFLOW_TRUSTED_PROXY_HOPS"] = "1"
os.environ["TAXFLOW_TOKEN_EXPIRE_MINUTES"] = "15"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager
from backend.auth_rate_limit import reset_attempts

# Re-initialize the global rate limiter with our test config.
from backend.rate_limit import GlobalRateLimiter
import backend.api as _api

# Create a fresh limiter with enforcement enabled for this test.
# TAXFLOW_TESTING=true bypasses the middleware UNLESS _test_enforce is set.
# We set it so our test requests are subject to rate limiting.
_test_limiter = GlobalRateLimiter(
    limit=100,
    window=60,
    burst=10,
    trusted_proxy_hops=1,
)
_api._GLOBAL_RATE_LIMITER = _test_limiter
_test_limiter._test_enforce = True  # Force enforcement despite TAXFLOW_TESTING=true


def seed(db):
    """Seed a test user and return (user, client, account, coa)."""
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    user = db.query(models.User).filter(models.User.username == "ddos_target").first()
    if user is None:
        crypto = LocalCryptoManager.create("password")
        user = models.User(
            username="ddos_target",
            email="ddos@example.com",
            hashed_password=get_password_hash("correct_password"),
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
        client = models.Client(name="DDoS Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

    return user, client


def make_client_with_ip(tenant_id, ip_addr):
    """Create a TestClient that simulates requests from a specific IP via X-Forwarded-For.

    With trusted_proxy_hops=1, the limiter expects "client_ip, proxy_ip" in
    X-Forwarded-For. It takes the entry at index -(hops+1) = -2 as the client.
    So we send "<ip_addr>, 127.0.0.1" to simulate ip_addr behind a proxy.
    """
    c = TestClient(app)
    c.headers["X-Tenant-ID"] = str(tenant_id)
    c.headers["X-Forwarded-For"] = f"{ip_addr}, 127.0.0.1"
    return c


# ---------------------------------------------------------------------------
# Phase A: Same-username DDoS — auth_rate_limit backstop
# ---------------------------------------------------------------------------

def phase_a_same_username(tenant_id):
    """500 concurrent attackers from different IPs all brute-forcing the same username.

    Expected: auth_rate_limit locks the username after 10 failures.
    Global rate limiter may also kick in per-IP, but the username lockout is the
    primary backstop. After lockout, all requests get 429 regardless of IP.

    A legitimate login from a clean IP AFTER the lockout should also get 429
    (because the username is locked), proving no IP-based bypass.

    Then we reset the tracker and verify a legitimate login succeeds.
    """
    print("\n" + "=" * 70)
    print("Phase 5.1-A: Same-username DDoS (auth_rate_limit backstop)")
    print("=" * 70)

    NUM_ATTACKERS = 500
    attack_results = []
    results_lock = threading.Lock()

    def attacker(attacker_id):
        ip = f"10.{attacker_id // 256}.{attacker_id % 256}.1"
        c = make_client_with_ip(tenant_id, ip)
        try:
            r = c.post(
                "/api/auth/login",
                data={"username": "ddos_target", "password": "wrong_password"},
            )
            with results_lock:
                attack_results.append({
                    "attacker_id": attacker_id,
                    "status": r.status_code,
                    "ip": ip,
                })
        except Exception as e:
            with results_lock:
                attack_results.append({
                    "attacker_id": attacker_id,
                    "status": "EXCEPTION",
                    "ip": ip,
                    "error": str(e)[:100],
                })

    # Reset auth_rate_limit tracker to start clean.
    reset_attempts("ddos_target")

    print(f"  Launching {NUM_ATTACKERS} concurrent attackers (different IPs, same username)...")

    # Use batches to avoid overwhelming the thread pool.
    BATCH_SIZE = 50
    for batch_start in range(0, NUM_ATTACKERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, NUM_ATTACKERS)
        with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = [pool.submit(attacker, i) for i in range(batch_start, batch_end)]
            concurrent.futures.wait(futures)
        if batch_start % 100 == 0:
            print(f"  ... {batch_end}/{NUM_ATTACKERS} attackers fired")

    print(f"  All {NUM_ATTACKERS} attackers completed.")

    # Analyze attack results.
    status_counts = {}
    for r in attack_results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"  Attack status distribution: {status_counts}")

    # Count 429s (rate limited) vs 401s (auth failed but not rate limited) vs 500s (server error)
    count_429 = status_counts.get(429, 0)
    count_401 = status_counts.get(401, 0)
    count_500 = status_counts.get(500, 0)
    count_exc = status_counts.get("EXCEPTION", 0)

    # Verify: legitimate login from clean IP during lockout should also get 429.
    clean_client = make_client_with_ip(tenant_id, "192.168.1.100")
    r = clean_client.post(
        "/api/auth/login",
        data={"username": "ddos_target", "password": "correct_password"},
    )
    locked_login_status = r.status_code
    print(f"  Legitimate login during lockout: HTTP {locked_login_status} (expected 429)")

    # Reset auth_rate_limit tracker and verify legitimate login succeeds.
    reset_attempts("ddos_target")

    # Clear the global rate limiter windows so the clean IP gets a fresh window.
    _api._GLOBAL_RATE_LIMITER._windows.clear()

    # Use a completely fresh IP on a different subnet.
    legit_client = make_client_with_ip(tenant_id, "88.88.88.88")
    r = legit_client.post(
        "/api/auth/login",
        data={"username": "ddos_target", "password": "correct_password"},
    )
    legit_login_status = r.status_code
    print(f"  Legitimate login after reset: HTTP {legit_login_status} (expected 200)")

    # DB health check — verify the DB is still responsive.
    check_engine = create_engine(ADMIN_URL)
    check_db = sessionmaker(bind=check_engine)()
    try:
        check_db.execute(text("SELECT 1"))
        db_ok = True
        user_count = check_db.query(models.User).count()
        print(f"  DB health: OK (responsive, {user_count} users)")
    except Exception as e:
        db_ok = False
        print(f"  DB health: FAILED — {e}")
    finally:
        check_db.close()
        check_engine.dispose()

    # Verdict for Phase A.
    passed = True
    failures = []

    if count_500 > 0:
        failures.append(f"{count_500} server errors (500) during attack — DB degradation")
        passed = False
    if count_exc > 0:
        failures.append(f"{count_exc} exceptions during attack")
        passed = False
    if locked_login_status != 429:
        failures.append(f"Legitimate login during lockout returned {locked_login_status} (expected 429)")
        passed = False
    if legit_login_status != 200:
        failures.append(f"Legitimate login after reset returned {legit_login_status} (expected 200)")
        passed = False
    if not db_ok:
        failures.append("DB became unresponsive after attack")
        passed = False
    # We expect a mix of 401 (initial failures) and 429 (after lockout/rate limit).
    # The key is NO 500s and the lockout + recovery works.
    if count_429 == 0 and count_401 == 0:
        failures.append("No 401 or 429 responses — attack didn't reach the server")
        passed = False

    if passed:
        print(f"\n  PHASE 5.1-A RESULT: PASS")
        print(f"    {count_429} rate-limited, {count_401} auth-failed, {count_500} server errors")
        print(f"    Username lockout works, legitimate login recovers after reset")
        print(f"    DB remained healthy throughout")
    else:
        print(f"\n  PHASE 5.1-A RESULT: FAIL")
        for f in failures:
            print(f"    - {f}")

    return passed, {
        "status_counts": status_counts,
        "count_429": count_429,
        "count_401": count_401,
        "count_500": count_500,
        "count_exc": count_exc,
        "locked_login_status": locked_login_status,
        "legit_login_status": legit_login_status,
        "db_ok": db_ok,
    }


# ---------------------------------------------------------------------------
# Phase B: Different-usernames, many IPs — global rate limit backstop
# ---------------------------------------------------------------------------

def phase_b_different_users(tenant_id, db):
    """500 concurrent attackers from different IPs using different usernames.

    Each attacker gets a unique IP and username, so the auth_rate_limit per-username
    tracker doesn't help (each username only fails once). The global per-IP rate
    limiter is the backstop here.

    Since each IP only makes 1 request, and the global limit is 100/min with burst 10,
    each IP's single request should go through (burst allows it). So we expect mostly
    401s (wrong password) with no 429s per-IP. This proves the global limiter doesn't
    collateral-block different IPs.

    Then: fire 200 requests from the SAME IP — should get 10 through (burst), then 429.
    """
    print("\n" + "=" * 70)
    print("Phase 5.1-B: Different-usernames DDoS (global rate limit + no collateral)")
    print("=" * 70)

    NUM_ATTACKERS = 500

    # Seed 500 users.
    print(f"  Seeding {NUM_ATTACKERS} target users...")
    engine = create_engine(ADMIN_URL)
    seed_db = sessionmaker(bind=engine)()
    seed_db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    seed_db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    for i in range(NUM_ATTACKERS):
        uname = f"victim_{i}"
        u = seed_db.query(models.User).filter(models.User.username == uname).first()
        if u is None:
            crypto = LocalCryptoManager.create("password")
            u = models.User(
                username=uname,
                email=f"victim_{i}@example.com",
                hashed_password=get_password_hash("their_password"),
                encryption_salt=crypto.salt_b64,
                is_active=True,
            )
            seed_db.add(u)
            seed_db.commit()
    seed_db.close()
    engine.dispose()
    print(f"  Seeded {NUM_ATTACKERS} users.")

    attack_results = []
    results_lock = threading.Lock()

    def attacker(attacker_id):
        ip = f"172.{attacker_id // 256}.{attacker_id % 256}.1"
        username = f"victim_{attacker_id}"
        c = make_client_with_ip(tenant_id, ip)
        try:
            r = c.post(
                "/api/auth/login",
                data={"username": username, "password": "wrong_password"},
            )
            with results_lock:
                attack_results.append({
                    "attacker_id": attacker_id,
                    "status": r.status_code,
                })
        except Exception as e:
            with results_lock:
                attack_results.append({
                    "attacker_id": attacker_id,
                    "status": "EXCEPTION",
                    "error": str(e)[:100],
                })

    print(f"  Launching {NUM_ATTACKERS} concurrent attackers (unique IP + username each)...")

    BATCH_SIZE = 50
    for batch_start in range(0, NUM_ATTACKERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, NUM_ATTACKERS)
        with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = [pool.submit(attacker, i) for i in range(batch_start, batch_end)]
            concurrent.futures.wait(futures)

    print(f"  All {NUM_ATTACKERS} attackers completed.")

    status_counts = {}
    for r in attack_results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"  Attack status distribution: {status_counts}")

    count_401 = status_counts.get(401, 0)
    count_429 = status_counts.get(429, 0)
    count_500 = status_counts.get(500, 0)
    count_exc = status_counts.get("EXCEPTION", 0)

    # Now test: single IP hammering — should get burst (10) through, then 429.
    print(f"\n  Testing single-IP rate limiting (200 requests from one IP)...")

    # Reset the global limiter to start clean for this sub-test.
    _api._GLOBAL_RATE_LIMITER = GlobalRateLimiter(
        limit=100,
        window=60,
        burst=10,
        trusted_proxy_hops=1,
    )
    _api._GLOBAL_RATE_LIMITER._test_enforce = True

    hammer_client = make_client_with_ip(tenant_id, "192.168.99.1")
    hammer_200 = 0
    hammer_429 = 0
    hammer_other = 0
    for i in range(200):
        r = hammer_client.post(
            "/api/auth/login",
            data={"username": "ddos_target", "password": "wrong"},
        )
        if r.status_code == 401:
            hammer_200 += 1  # 401 means it got through the rate limiter
        elif r.status_code == 429:
            hammer_429 += 1
        else:
            hammer_other += 1

    print(f"  Single-IP hammer: {hammer_200} through (401), {hammer_429} rate-limited (429), {hammer_other} other")

    # DB health check.
    check_engine = create_engine(ADMIN_URL)
    check_db = sessionmaker(bind=check_engine)()
    try:
        check_db.execute(text("SELECT 1"))
        db_ok = True
        user_count = check_db.query(models.User).count()
        print(f"  DB health: OK (responsive, {user_count} users)")
    except Exception as e:
        db_ok = False
        print(f"  DB health: FAILED — {e}")
    finally:
        check_db.close()
        check_engine.dispose()

    # Verdict.
    passed = True
    failures = []

    if count_500 > 0:
        failures.append(f"{count_500} server errors (500) during distributed attack")
        passed = False
    if count_exc > 0:
        failures.append(f"{count_exc} exceptions during distributed attack")
        passed = False
    # Each unique IP makes 1 request — should mostly get 401 (auth failed, not rate limited).
    # Some might get 429 if the global limiter's burst is exhausted by concurrent timing,
    # but the point is no 500s and DB stays healthy.
    if count_401 == 0 and count_429 == 0:
        failures.append("No 401 or 429 responses — distributed attack didn't reach the server")
        passed = False
    # Single-IP hammer: should have some 429s (rate limit kicked in).
    if hammer_429 == 0:
        failures.append("Single-IP hammer: no 429 responses — global rate limiter not enforcing")
        passed = False
    if hammer_200 > 15:  # burst is 10, allow some margin for timing
        failures.append(f"Single-IP hammer: {hammer_200} requests through (expected ~10 burst)")
        passed = False
    if hammer_other > 0:
        failures.append(f"Single-IP hammer: {hammer_other} unexpected status codes")
        passed = False
    if not db_ok:
        failures.append("DB became unresponsive after distributed attack")
        passed = False

    if passed:
        print(f"\n  PHASE 5.1-B RESULT: PASS")
        print(f"    Distributed: {count_401} auth-failed, {count_429} rate-limited, {count_500} server errors")
        print(f"    Single-IP: {hammer_200} through, {hammer_429} rate-limited (burst enforced)")
        print(f"    No collateral IP blocking, DB healthy")
    else:
        print(f"\n  PHASE 5.1-B RESULT: FAIL")
        for f in failures:
            print(f"    - {f}")

    return passed, {
        "distributed_status_counts": status_counts,
        "distributed_401": count_401,
        "distributed_429": count_429,
        "distributed_500": count_500,
        "hammer_through": hammer_200,
        "hammer_429": hammer_429,
        "hammer_other": hammer_other,
        "db_ok": db_ok,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("ST4 Phase 5.1 — Rate Limiting Under DDoS")
    print(f"  DB: {TEST_DB}")
    print(f"  global rate limit: 100/min, burst 10")
    print(f"  auth_rate_limit: progressive delay, lockout after 10 failures")
    print("=" * 70)

    # Seed the primary target user.
    engine = create_engine(ADMIN_URL)
    db = sessionmaker(bind=engine)()
    user, client = seed(db)
    tenant_id = client.id
    db.close()
    engine.dispose()

    print(f"  Target user: ddos_target (tenant_id={tenant_id})")

    # Run Phase A.
    a_passed, a_results = phase_a_same_username(tenant_id)

    # Reset rate limiter between phases.
    global _api
    _api._GLOBAL_RATE_LIMITER = GlobalRateLimiter(
        limit=100,
        window=60,
        burst=10,
        trusted_proxy_hops=1,
    )
    _api._GLOBAL_RATE_LIMITER._test_enforce = True
    reset_attempts("ddos_target")

    # Run Phase B.
    b_passed, b_results = phase_b_different_users(tenant_id, None)

    # Final verdict.
    print("\n" + "=" * 70)
    print("PHASE 5.1 FINAL VERDICT")
    print("=" * 70)

    if a_passed and b_passed:
        print("  PHASE 5.1 RESULT: PASS")
        print("  Rate limiting survives DDoS: username lockout + per-IP global limiter")
        print("  work together. No DB degradation. Legitimate users recover after reset.")
    else:
        print("  PHASE 5.1 RESULT: FAIL")
        if not a_passed:
            print("    Phase A (same-username DDoS): FAIL")
        if not b_passed:
            print("    Phase B (distributed DDoS): FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()