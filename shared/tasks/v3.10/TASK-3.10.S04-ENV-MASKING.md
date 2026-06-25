# TASK-3.10.S04 — Sensitive Data in Process Arguments

**Owner:** TBD  
**Goal:** Ensure secrets like `DATABASE_URL` passwords are not visible in process listings.

## Files

- `backend/database.py`
- `backend/config.py`
- `scripts/start_server.py`
- `backend/tests/test_env_masking.py`

## Requirements

1. Load secrets from environment only; never pass them as CLI args.
2. Mask secrets in any logging or error output.
3. Document secure startup pattern.

## Tests

- `DATABASE_URL` password not in `/proc/*/cmdline`.
- Secrets redacted in logs.

## Report

Files changed, startup doc updated, test results.
