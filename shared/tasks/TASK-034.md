# TASK-034 Completion Handoff — Timing-Attack-Safe Authentication

**Status:** ✅ Complete
**Owner:** Jane
**Completed:** 2026-06-22
**Project:** TaxFlow Pro v3.9.2 Security Hardening

## Objective
Eliminate timing side-channels and response-text leakage on the local authentication path (`/api/auth/login` and `/api/auth/login-json`).

## Changes Made

### 1. New module: `backend/security/timing_safe.py`
- `constant_time_compare(a, b)` — HMAC `compare_digest` wrapper for str/bytes.
- `constant_time_verify_password(plain, hashed)` — always runs `bcrypt.checkpw` against a real hash; uses a dummy hash when no user exists so the failure path performs identical work.
- `constant_time_user_lookup(db, username)` — fetches the first (and only) local user and compares the supplied username in constant time. Returns a `_SentinelUser` when the database is empty so callers never branch on existence.
- `_SentinelUser` — stand-in with a fixed-length padded username and a valid dummy bcrypt hash.

### 2. Updated: `backend/routers/auth.py`
- Replaced direct `verify_password` and `User.query.filter(...)` lookup with `_timing_safe_authenticate()`.
- `/auth/login` (OAuth2 form) and `/auth/login-json` now use the constant-time path.
- `/auth/boot` (already-initialized path) runs a dummy authentication before returning the uniform `400 Already initialized` error.
- Invalid username, wrong password, and missing user all return identical 401 status and detail text.

### 3. Tests: `backend/tests/test_timing_safe.py`
- Constant-time comparison correctness.
- Login timing uniformity between valid and invalid usernames (median divergence < 20%).
- Response status and detail uniformity.
- Sentinel user behavior for empty database.

## Test Results

```text
python -m pytest backend/tests/test_timing_safe.py -v
8 passed, 4 warnings in 29.86s
```

## Files Changed
- `backend/security/timing_safe.py`
- `backend/routers/auth.py`
- `backend/tests/test_timing_safe.py`

## Notes
- The initial implementation returned `None` for an empty database; the test contract expected a sentinel, so `constant_time_user_lookup` was updated to return `_SentinelUser()`.
- `_timing_safe_authenticate` was updated to use `hasattr(user, "hashed_password")` and `isinstance(user, models.User)` so it handles both real users and sentinels safely.
- Timing test can be sensitive to host load; the 20% threshold is a defense-in-depth guard, not a cryptographic guarantee.

## Next Step
Proceed to TASK-035 (Temporary File Cleanup) per the v3.9.2 roadmap.

## Roadmap Reference
`projects/TaxFlow-Pro/TaxFlow-Pro-v3.9/shared/specs/v3.9.2-roadmap.md`
