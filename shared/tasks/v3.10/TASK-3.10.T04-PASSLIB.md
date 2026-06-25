# TASK-3.10.T04 — passlib / Argon2 Password Hashing

**Owner:** TBD  
**Goal:** Replace custom SHA-3_256 + salt hashing with passlib using Argon2id.

## Files

- `backend/local/auth.py`
- `backend/routers/auth.py`
- `backend/tests/test_argon2_auth.py`

## Requirements

1. Use `passlib[argon2]` with Argon2id.
2. Migrate existing SHA-3 hashes on next successful login (re-hash and store).
3. Password verify function must be constant-time.

## Tests

- New passwords hash with Argon2id.
- Old SHA-3 hash verifies and is re-hashed.
- Verify function is timing-attack resistant.
- Invalid password fails.

## Report

Files changed, migration strategy, test results.
