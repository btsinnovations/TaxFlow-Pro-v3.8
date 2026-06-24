# TASK-004: Auth Session Store + Token Validation

## Status
Inbox

## Goal
Close the P0 security gap identified in the v3.9 gap analysis: current v3.7/v3.9 hybrid auth either accepts opaque tokens with no per-user binding (v3.7 `LocalAuthManager`) or issues JWTs without server-side revocation. Add a local session store and validate every protected request against it.

## Options
1. Restore proper JWT validation with expiry and `sub` claim (already partially done in v3.9 `auth.py`) PLUS add a `sessions` table for revocation.
2. Build a real local session store (token hash → user_id → expiry → revoked_at) and rewrite `_get_current_user()` to validate against it.

## Deliverables
1. `backend/models.py` — `Session` table
2. `backend/auth.py` or `backend/local/sessions.py` — session creation/validation/revocation helpers
3. Updated `backend/routers/auth.py` — `/auth/login`, `/auth/logout`, `/auth/me` use session store
4. Tests in `backend/tests/test_sessions.py`

## Acceptance Criteria
- Any well-formed Bearer token without a matching session hash returns 401
- `/auth/logout` invalidates the server-side session
- Sessions have expiry and auto-expire
- Existing test suite still passes
