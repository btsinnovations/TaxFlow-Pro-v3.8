# TASK-3.10.S02 — Timing-Attack-Safe Authentication

**Owner:** TBD  
**Goal:** Ensure login endpoint does not leak username existence via timing differences.

## Files

- `backend/routers/auth.py`
- `backend/local/auth.py`
- `backend/tests/test_login_timing.py`

## Requirements

1. Always perform a dummy password hash verification for missing users.
2. Return identical HTTP status and response time whether user exists or not.
3. Log failed attempts without exposing existence.

## Tests

- Timing distribution for valid vs invalid username is statistically indistinguishable.
- Same response code and body for both cases.

## Report

Files changed, timing test methodology, results.
