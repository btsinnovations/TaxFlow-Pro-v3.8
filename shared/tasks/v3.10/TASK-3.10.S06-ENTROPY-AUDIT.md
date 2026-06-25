# TASK-3.10.S06 — Weak Entropy Audit

**Owner:** TBD  
**Goal:** Ensure all key/token generation uses `secrets`, not `random`.

## Files

- All modules generating tokens, salts, keys
- `backend/tests/test_entropy.py`

## Requirements

1. Search codebase for `random` usage in security contexts.
2. Replace with `secrets.token_*` or `os.urandom`.
3. Ensure salt/key lengths meet current minimums.

## Tests

- No `random` calls in token/key/salt generation.
- Tokens have sufficient length (>=32 bytes).

## Report

Files changed, violations found, fixes applied.
