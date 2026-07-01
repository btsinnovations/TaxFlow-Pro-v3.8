"""Stress Test 4 Phase 5.2 — JWT Thrashing & Revocation.

Fire 1,000 valid JWTs; revoke user session halfway.
Backend immediately rejects remaining tokens; no grace-period caching.

Run:
    set ST4_TEST_DB=st4_p52
    python st4_p5_2_jwt_revocation.py
"""
import os
import sys
import time
import threading
import concurrent.futures
from datetime import date

# Force UTF-8 stdout to avoid cp1252 encoding errors on Windows console.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEST_DB = os.environ.get("ST4_TEST_DB")
if not TEST_DB:
    print("Set ST4_TEST_DB env var (e.g. set ST4_TEST_DB=st4_p52)")
    sys.exit(1)

TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "false"
os.environ["TAXFLOW_TESTING"] = "true"
os.environ["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
os.environ["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
os.environ["TAXFLOW_TOKEN_EXPIRE_MINUTES"] = "15"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager
from backend.auth import create_access_token, revoke_access_token, decode_access_token
from backend.database import SessionLocal

# Disable the test-bypass for global rate limiting since we want real behavior.
# But keep TAXFLOW_TESTING=true so the limiter is disabled (we don't want rate
# limiting interfering with 1000 JWT requests).
import backend.api as _api
_api._GLOBAL_RATE_LIMITER.check = lambda remote_addr, headers: None


def seed(db):
    """Seed a test user and return (user, client)."""
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    user = db.query(models.User).filter(models.User.username == "jwt_chaos").first()
    if user is None:
        crypto = LocalCryptoManager.create("password")
        user = models.User(
            username="jwt_chaos",
            email="jwt@example.com",
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
        client = models.Client(name="JWT Chaos Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

    return user, client


def main():
    print("=" * 70)
    print("ST4 Phase 5.2 — JWT Thrashing & Revocation")
    print(f"  DB: {TEST_DB}")
    print(f"  tokens to issue: 1000")
    print(f"  revoke at midpoint: 500")
    print("=" * 70)

    # Seed user.
    engine = create_engine(ADMIN_URL)
    db = sessionmaker(bind=engine)()
    user, client = seed(db)
    user_id = user.id
    tenant_id = client.id
    db.close()
    engine.dispose()

    print(f"  Target user: jwt_chaos (id={user_id}, tenant_id={tenant_id})")

    # -----------------------------------------------------------------------
    # Step 1: Issue 1,000 valid JWTs (each bound to a server-side Session row).
    # -----------------------------------------------------------------------
    print(f"\n  Issuing 1,000 access tokens (each creates a Session row)...")

    issue_engine = create_engine(TEST_URL, pool_size=10, max_overflow=20)
    IssueSession = sessionmaker(bind=issue_engine)

    tokens = []
    issue_start = time.monotonic()
    for i in range(1000):
        s = IssueSession()
        try:
            token = create_access_token(user_id, db=s)
            tokens.append(token)
        finally:
            s.close()
    issue_elapsed = time.monotonic() - issue_start
    print(f"  Issued 1,000 tokens in {issue_elapsed:.2f}s ({1000/issue_elapsed:.0f} tokens/s)")

    # Verify all tokens are initially valid.
    verify_engine = create_engine(TEST_URL, pool_size=10, max_overflow=20)
    VerifySession = sessionmaker(bind=verify_engine)

    print(f"  Verifying all 1,000 tokens are initially valid...")
    valid_count = 0
    s = VerifySession()
    try:
        for t in tokens:
            payload = decode_access_token(t, db=s)
            if payload is not None:
                valid_count += 1
    finally:
        s.close()
    print(f"  Valid tokens before revocation: {valid_count}/1000")

    if valid_count != 1000:
        print(f"  FAIL: Expected 1000 valid tokens, got {valid_count}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 2: Fire 500 concurrent requests with the first 500 tokens.
    # Then revoke ALL sessions for the user.
    # Then fire 500 concurrent requests with the remaining 500 tokens.
    # -----------------------------------------------------------------------

    results_before = []
    results_after = []
    results_lock = threading.Lock()

    def hit_endpoint(token_id, token, results_list):
        """Hit /api/auth/me with a token and record the status."""
        c = TestClient(app)
        c.headers["X-Tenant-ID"] = str(tenant_id)
        c.headers["Authorization"] = f"Bearer {token}"
        try:
            r = c.get("/api/auth/me")
            with results_lock:
                results_list.append({
                    "token_id": token_id,
                    "status": r.status_code,
                })
        except Exception as e:
            with results_lock:
                results_list.append({
                    "token_id": token_id,
                    "status": "EXCEPTION",
                    "error": str(e)[:100],
                })

    # Phase A: Fire first 500 tokens concurrently (should all succeed).
    print(f"\n  Phase A: Firing 500 concurrent requests (pre-revocation)...")
    phase_a_start = time.monotonic()

    BATCH_SIZE = 50
    for batch_start in range(0, 500, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, 500)
        with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = [
                pool.submit(hit_endpoint, i, tokens[i], results_before)
                for i in range(batch_start, batch_end)
            ]
            concurrent.futures.wait(futures)

    phase_a_elapsed = time.monotonic() - phase_a_start
    before_200 = sum(1 for r in results_before if r["status"] == 200)
    before_401 = sum(1 for r in results_before if r["status"] == 401)
    before_500 = sum(1 for r in results_before if r["status"] == 500)
    before_exc = sum(1 for r in results_before if r["status"] == "EXCEPTION")
    print(f"  Phase A complete in {phase_a_elapsed:.2f}s: {before_200} ok, {before_401} rejected, {before_500} errors, {before_exc} exceptions")

    # -----------------------------------------------------------------------
    # REVOCATION: Revoke ALL sessions for the user.
    # -----------------------------------------------------------------------
    print(f"\n  >>> REVOKING ALL SESSIONS FOR USER {user_id} <<<")

    revoke_engine = create_engine(ADMIN_URL)
    RevokeSession = sessionmaker(bind=revoke_engine)
    revoke_db = RevokeSession()
    try:
        revoke_db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
        revoke_db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

        # Bulk-revoke all active sessions for this user.
        revoked_count = revoke_db.execute(text(
            "UPDATE sessions SET revoked_at = NOW() WHERE user_id = :uid AND revoked_at IS NULL"
        ), {"uid": user_id}).rowcount
        revoke_db.commit()
        print(f"  Bulk-revoked {revoked_count} active sessions")

        # Also add all JTIs to the revoked_tokens table for belt-and-suspenders.
        # The decode_access_token checks both Session.revoked_at and RevokedToken.
        sessions = revoke_db.execute(text(
            "SELECT token_jti FROM sessions WHERE user_id = :uid"
        ), {"uid": user_id}).fetchall()

        for row in sessions:
            jti = row[0]
            if jti:
                existing = revoke_db.query(models.RevokedToken).filter(
                    models.RevokedToken.jti == jti
                ).first()
                if not existing:
                    rt = models.RevokedToken(
                        jti=jti,
                        user_id=user_id,
                        token_type="access",
                        revoked_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
                    )
                    revoke_db.add(rt)
        revoke_db.commit()
        print(f"  Added {len(sessions)} JTIs to revoked_tokens table")
    finally:
        revoke_db.close()
        revoke_engine.dispose()

    # Short delay to ensure DB writes are visible.
    time.sleep(0.5)

    # -----------------------------------------------------------------------
    # Phase B: Fire remaining 500 tokens concurrently (should ALL get 401).
    # -----------------------------------------------------------------------
    print(f"\n  Phase B: Firing 500 concurrent requests (post-revocation)...")
    phase_b_start = time.monotonic()

    for batch_start in range(500, 1000, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, 1000)
        with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = [
                pool.submit(hit_endpoint, i, tokens[i], results_after)
                for i in range(batch_start, batch_end)
            ]
            concurrent.futures.wait(futures)

    phase_b_elapsed = time.monotonic() - phase_b_start
    after_200 = sum(1 for r in results_after if r["status"] == 200)
    after_401 = sum(1 for r in results_after if r["status"] == 401)
    after_500 = sum(1 for r in results_after if r["status"] == 500)
    after_exc = sum(1 for r in results_after if r["status"] == "EXCEPTION")
    print(f"  Phase B complete in {phase_b_elapsed:.2f}s: {after_200} ok, {after_401} rejected, {after_500} errors, {after_exc} exceptions")

    # -----------------------------------------------------------------------
    # Verify: re-test the first 500 tokens too (should also be 401 now).
    # -----------------------------------------------------------------------
    print(f"\n  Verifying first 500 tokens are also revoked after bulk revocation...")
    retest_results = []
    for batch_start in range(0, 500, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, 500)
        with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SIZE) as pool:
            futures = [
                pool.submit(hit_endpoint, i, tokens[i], retest_results)
                for i in range(batch_start, batch_end)
            ]
            concurrent.futures.wait(futures)

    retest_200 = sum(1 for r in retest_results if r["status"] == 200)
    retest_401 = sum(1 for r in retest_results if r["status"] == 401)
    retest_500 = sum(1 for r in retest_results if r["status"] == 500)
    print(f"  Retest: {retest_200} ok, {retest_401} rejected, {retest_500} errors")

    # -----------------------------------------------------------------------
    # DB health check.
    # -----------------------------------------------------------------------
    check_engine = create_engine(ADMIN_URL)
    check_db = sessionmaker(bind=check_engine)()
    try:
        check_db.execute(text("SELECT 1"))
        db_ok = True
        session_count = check_db.query(models.Session).filter(
            models.Session.user_id == user_id
        ).count()
        revoked_session_count = check_db.query(models.Session).filter(
            models.Session.user_id == user_id,
            models.Session.revoked_at.isnot(None)
        ).count()
        print(f"  DB health: OK (responsive, {session_count} sessions, {revoked_session_count} revoked)")
    except Exception as e:
        db_ok = False
        print(f"  DB health: FAILED — {e}")
    finally:
        check_db.close()
        check_engine.dispose()

    # -----------------------------------------------------------------------
    # Verdict
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PHASE 5.2 VERDICT")
    print("=" * 70)

    passed = True
    failures = []

    # 1. All 500 pre-revocation requests should succeed (200).
    if before_200 != 500:
        failures.append(f"Pre-revocation: expected 200 successes, got {before_200}")
        passed = False
    else:
        print(f"  ✅ Pre-revocation: all 500 tokens accepted")

    # 2. All 500 post-revocation requests should fail (401).
    if after_200 > 0:
        failures.append(f"Post-revocation: {after_200} tokens still accepted (grace-period caching detected!)")
        passed = False
    else:
        print(f"  ✅ Post-revocation: all {after_401} tokens rejected immediately")

    # 3. Retest of first 500 should also be 401.
    if retest_200 > 0:
        failures.append(f"Retest: {retest_200} tokens from first batch still accepted after revocation")
        passed = False
    else:
        print(f"  ✅ Retest: all {retest_401} first-batch tokens also rejected")

    # 4. No 500 errors.
    total_500 = before_500 + after_500 + retest_500
    if total_500 > 0:
        failures.append(f"{total_500} server errors (500) during test")
        passed = False
    else:
        print(f"  ✅ No server errors (500) throughout test")

    # 5. No exceptions.
    total_exc = before_exc + after_exc + sum(1 for r in retest_results if r["status"] == "EXCEPTION")
    if total_exc > 0:
        failures.append(f"{total_exc} exceptions during test")
        passed = False
    else:
        print(f"  ✅ No exceptions throughout test")

    # 6. DB healthy.
    if not db_ok:
        failures.append("DB became unresponsive")
        passed = False
    else:
        print(f"  ✅ DB remained healthy ({session_count} sessions, {revoked_session_count} revoked)")

    # 7. No grace-period caching — immediate rejection.
    if after_401 == 500 and after_200 == 0:
        print(f"  ✅ Zero grace-period accepts — immediate rejection confirmed")
    else:
        failures.append("Grace-period caching detected — some tokens accepted after revocation")
        passed = False

    if passed:
        print(f"\n  PHASE 5.2 RESULT: PASS")
        print(f"  JWT revocation is immediate and comprehensive. Bulk session revocation")
        print(f"  rejects all existing tokens with zero grace period. No caching bypass.")
    else:
        print(f"\n  PHASE 5.2 RESULT: FAIL")
        for f in failures:
            print(f"    - {f}")

    # Cleanup.
    issue_engine.dispose()
    verify_engine.dispose()

    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()