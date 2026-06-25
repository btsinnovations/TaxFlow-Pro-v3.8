# TASK-3.10.T06 — pydantic-settings Config

**Owner:** TBD  
**Goal:** Centralize environment/configuration management with `pydantic-settings`.

## Files

- `backend/config.py` — unified Pydantic settings module
- `backend/database.py`
- `backend/local/settings.py`
- `backend/tests/test_settings.py`

## Requirements

1. Replace scattered `os.environ.get()` calls.
2. Load `.env` files consistently.
3. Validate types and required fields at startup.
4. Mask secrets in logs and error output.

## Tests

- All required env vars validated at startup.
- Missing required var fails fast with clear message.
- Secrets are not printed in `repr()` or logs.

## Report

Files changed, settings schema summary, migration notes.
