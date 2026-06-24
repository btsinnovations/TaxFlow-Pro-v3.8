# TASK-037 — Phase 3 Foundation (3.4c / 3.4f / 3.4g / 3.4h)

## Status
**Complete.**

## Approved by
Josh via `btsinnovations` on 2026-06-22.

## Scope
Implement the approved first slice of Phase 3 from `docs/TODO_FIRST.md`:
- 3.4c — Bind local server to `127.0.0.1` by default.
- 3.4f — Harden `.local_secret` storage with restrictive permissions and local-root placement.
- 3.4g — Replace placeholder token acceptance with real server-side session validation.
- 3.4h — Fix Windows ACL bug in the 3.4f fallback path.

## Work Done

### 3.4c — Local server bind
- `backend/api.py` uvicorn block defaults to `127.0.0.1:8000`.
- LAN bind opt-in via `TAXFLOW_BIND_LAN=true` or `UVICORN_HOST`/`UVICORN_PORT` overrides.
- Updated `README.md` and `start.sh` to reflect loopback default.

### 3.4f — Harden `.local_secret` storage
- `backend/local/keyring_secret.py` stores `.local_secret` under `LOCAL_ROOT` (via `get_local_path`).
- Supports `TAXFLOW_LOCAL_SECRET_FILE` override.
- Creates parent directories on first write.
- POSIX permissions set to `0o600`; Windows fallback uses owner-only DACL.

### 3.4h — Windows ACL fix
- Replaced non-existent `win32security.GetUserName()` with `win32api.GetUserName()`.
- Warning `Failed to harden Windows ACL on secret file: ...` no longer appears.

### 3.4g — Real session validation
- Added `Session` model in `backend/models.py` with:
  - `token_hash` (SHA-256 of the JWT, unique index)
  - `token_jti`, `user_id`, `expires_at`, `revoked_at`, `created_at`, `last_seen_at`, `ip_address`, `user_agent`
- `User.sessions` relationship added.
- `backend/auth.py`:
  - `create_access_token(user_id, expires_delta=None, db=None)` creates a server-side `Session` row when a DB session is supplied.
  - `decode_access_token(token, db=None)` validates the matching `Session` row (exists, not revoked, not expired).
  - `revoke_access_token` marks the matching `Session` row as revoked before recording the JTI.
  - `rotate_refresh_token` passes `db=db` when creating the new access token.
- `backend/routers/auth.py`:
  - `_get_current_user` calls `decode_access_token(token, db)` for server-side validation.
  - Added `_create_access_session(db, user_id)` helper.
  - `/boot`, `/login`, `/login-json`, `/refresh` now bind tokens to `Session` rows.
  - `/logout` revokes the session via `revoke_access_token`.
- Added focused tests in `backend/tests/test_hybrid_auth.py`:
  - `test_access_token_creates_server_side_session`
  - `test_missing_session_rejects_valid_signature`
  - `test_session_revoked_on_logout`
  - `test_fresh_login_after_logout_creates_new_session`

### Migration for PostgreSQL
- Added `alembic/versions/53e636150d46_add_server_side_sessions.py` as a child of `4f0bb0ee4bff`.
- Migration creates `sessions` table with indexes for `token_hash`, `token_jti`, and `user_id`.

### Documentation
- Updated `docs/TODO_FIRST.md` to mark 3.4g and 3.4h complete.
- Updated `CHANGES.md` with sections 24 (3.4c), 25 (3.4f), and 26 (3.4g).

## Verification

```powershell
python -m pytest backend/tests/test_hybrid_auth.py -q
# 35 passed, 10 warnings

python -m pytest backend/tests -q --tb=short
# 332 passed, 97 warnings, 0 failed
```

## Modified Files
- `backend/api.py`
- `README.md`
- `start.sh`
- `backend/local/keyring_secret.py`
- `backend/models.py`
- `backend/auth.py`
- `backend/routers/auth.py`
- `backend/tests/test_hybrid_auth.py`
- `backend/tests/test_migration_health.py`
- `alembic/versions/53e636150d46_add_server_side_sessions.py`
- `docs/TODO_FIRST.md`
- `CHANGES.md`

## Blockers
None.

## Next Steps (awaiting direction from James / Josh)
- Decide whether to continue with remaining 3.4 items (3.4a, 3.4b, 3.4d, 3.4e) or move to 3.3/3.7 (crypto + local auth) next.
