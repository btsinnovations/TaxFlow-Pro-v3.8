# TASK-026: TaxFlow Pro v3.9.2 — Refresh Token Rotation

## Status
**COMPLETE** — implementation, tests, and regression all green.

## Goal
Split access and refresh tokens, rotate refresh on use, revoke refresh family on theft/logout, and persist only SHA-256 hashes of opaque refresh tokens.

## Implementation Details
- `backend/models.py`: added `RefreshToken` table.
  - `token_hash` (unique, indexed), `user_id` (FK to users), `family_id` (UUID family, indexed).
  - `expires_at`, `created_at`, `revoked_at`, `replaced_by_token_hash`, `client_hash`.
- `backend/auth.py`:
  - `create_refresh_token(db, user_id)` creates and returns an opaque 64-byte URL-safe token; stores SHA-256 hash.
  - `rotate_refresh_token(db, old_token)` marks the old token as replaced, creates a new token in the same family. Reuse of a replaced/revoked token revokes the entire family.
  - `revoke_refresh_token(db, token)` and `revoke_refresh_family(db, token)`.
  - Access token default lifetime reduced to 15 minutes.
  - `_refresh_token_is_valid()` normalizes naive SQLite datetimes to UTC before comparison.
- `backend/routers/auth.py`:
  - `/boot`, `/login`, `/login-json` return `TokenPair` (access + refresh).
  - Added `POST /auth/refresh`.
  - `POST /auth/logout` revokes both access and refresh tokens when the refresh token is supplied.
- `backend/schemas.py`: added `RefreshRequest` and `TokenPair`.
- `backend/tests/test_refresh_tokens.py`: 7 tests covering boot/login pairs, rotation, old-token rejection, invalid token, logout revocation, and family theft detection.
- Alembic migrations:
  - `f2a9b8c1d4e5_add_refresh_tokens_table.py`
  - `842bfa1713f4_merge_audit_chain_hash_and_refresh_.py` (merge head reconciling `c4062c0c95ff` and `f2a9b8c1d4e5`).
- Configuration/docs:
  - `.env.example`: `TAXFLOW_TOKEN_EXPIRE_MINUTES=15`, `TAXFLOW_REFRESH_TOKEN_EXPIRE_DAYS=30`.
  - `README.md`: Authentication section updated.

## Test Results
- `pytest backend/tests/test_refresh_tokens.py backend/tests/test_hybrid_auth.py backend/tests/test_audit_trail.py backend/tests/test_append_only.py -v`: **42 passed, 0 failed**.
- `pytest backend/tests -q`: **228 passed, 0 failed**.

## Regression Fixes Required by TASK-026
- `backend/tests/test_local_first.py`: wrapped teardown `DELETE FROM audit_entries` in `_set_audit_entries_mutable()` so the append-only guard introduced in TASK-025 does not break test cleanup.
- `backend/tests/test_migration_health.py`: updated expected latest head from `2227f9254a8b` to `842bfa1713f4` after the merge migration was created.

## Security Properties
- Refresh tokens are opaque, high-entropy, single-use, and stored only as SHA-256 hashes.
- Reuse of a revoked or replaced refresh token revokes the entire family, preventing token replay.
- Logout revokes the access token via revoked-token table and the refresh token family via the refresh-token table.

## Notes
- No commit yet per orchestrator instruction; all v3.9.2 changes remain batched for the v3.9.2 release.
- Next task: **TASK-027: Security headers + CORS hardening**.
