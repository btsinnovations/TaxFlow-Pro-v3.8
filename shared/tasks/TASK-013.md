# TASK-013 — P0.2 OS Keyring Integration for `.local_secret`

## Status
**COMPLETE** — all deliverables implemented and tests passing.

## Files Changed
- `backend/local/keyring_secret.py` *(new)* — `store_secret`, `retrieve_secret`, `delete_secret`, and `migrate_file_secret` with `keyring` first + `.local_secret` fallback.
- `backend/auth.py` — `get_local_secret()` now:
  - honors `TAXFLOW_SECRET_KEY` env override,
  - migrates an existing `.local_secret` into the credential store,
  - uses keyring as default store,
  - falls back to `.local_secret` when keyring is unavailable.
- `backend/tests/test_keyring_secret.py` *(new)* — covers round-trip, fallback, migration, and secret-regeneration token invalidation.
- `backend/tests/test_hybrid_auth.py` — added autouse fixture that disables keyring so legacy file-only behavior stays deterministic.
- `backend/tests/conftest.py` — default test keyring backend fails so tests don't touch the real OS credential store.
- `requirements.txt` — added `keyring>=25.0.0`.
- `README.md` — updated Authentication section to document keyring-backed storage and `.local_secret` fallback.

## Test Results
```
pytest backend/tests/test_keyring_secret.py backend/tests/test_hybrid_auth.py -v
33 passed, 0 failed, 10 warnings in 73.55s
```

## Blockers
None.

## Notes
- No API contract changes to `/api/auth/boot`, `/api/auth/login`, or `/api/auth/change-password`.
- `.local_secret` fallback retained for headless/container use.
- No commit made per instruction; awaiting v3.9.2 batch commit.
