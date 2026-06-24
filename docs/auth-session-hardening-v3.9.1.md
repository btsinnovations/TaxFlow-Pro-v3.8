# TaxFlow Pro v3.9.1 — Auth Session Hardening

**Task:** TASK-035  
**Scope:** `backend/` only — session revocation and password-hash unification.

## Summary

Closed P0.2 from the v3.9.1 gap audit by:

1. Recording JWT `expires_at` in the revocation blocklist and adding cleanup.
2. Ensuring `/api/auth/logout` invalidates access tokens server-side.
3. Migrating `backend/local/auth.py` to bcrypt as the canonical hash algorithm while preserving one-way compatibility with legacy SHA-3_256 hashes.

## 1. JWT `jti` + Revocation Blocklist

`backend/auth.py` already issued access tokens with a `jti` claim and rejected revoked tokens in `decode_access_token`. The remaining gaps were:

- `RevokedToken.expires_at` was always `None`.
- No helper existed to prune stale blocklist entries.

Changes:

- `revoke_access_token()` now decodes `exp` from the JWT and stores `expires_at` as a timezone-aware UTC datetime.
- `_revoke_access_token_by_jti()` accepts optional `user_id` and `expires_at` and normalizes naive datetimes before persistence.
- New `cleanup_expired_revoked_tokens(db: Session) -> int` deletes revocation records whose `expires_at` has passed and returns the deletion count.

The `/api/auth/logout` endpoint in `backend/routers/auth.py` calls `revoke_access_token()`, so logged-out tokens are now recorded with an expiry and can be cleaned up later.

## 2. Server-Side Logout

`/api/auth/logout` behavior:

- Requires a valid access token (existing `_get_current_user` dependency).
- Extracts the token's `jti` and inserts it into `revoked_tokens`.
- Revokes the entire refresh-token family when a `refresh_token` is supplied.
- Clears the in-memory column-encryption manager via `logout_local_user()`.

Because `_get_current_user` rejects revoked tokens, calling `/logout` twice with the same access token returns `401` after the first call.

## 3. Password-Hash Stack Unification

**Decision:** bcrypt is canonical, matching `backend/auth.py` and `backend/routers/auth.py`.

`backend/local/auth.py` was the only remaining SHA-3_256 path. The migration strategy:

- `LocalAuthManager.hash_password()` now returns bcrypt.
- `LocalAuthManager.verify_password()` detects legacy SHA-3_256 hashes by their `salt_hex:hash_hex` format and verifies them.
- `LocalAuthManager.authenticate()` verifies the password; if the stored hash is legacy, it rehashes the password with bcrypt, overwrites the stored hash, and commits.
- SHA-3_256 hashing remains only as a private `_legacy_hash_password()` helper inside the verify path. It is never used for new hashes.

This gives users with legacy hashes a transparent, one-time migration without requiring a manual password reset.

## 4. Test Coverage

Extended `backend/tests/test_hybrid_auth.py`:

- `test_access_token_jti_is_unique` — two tokens have distinct `jti` values.
- `test_revoked_token_cleanup_prunes_expired_records` — expired blocklist rows are deleted.
- `TestLocalAuthHashMigration`:
  - `test_new_local_user_gets_bcrypt_hash`
  - `test_legacy_sha3_user_login_rehashes_to_bcrypt`
  - `test_verify_password_rejects_wrong_password_for_bcrypt_and_legacy`

Existing tests for logout revocation and `jti` presence continue to guard the blocklist behavior.

## Files Changed

- `backend/auth.py`
- `backend/local/auth.py`
- `backend/routers/auth.py`
- `backend/tests/test_hybrid_auth.py`
- `docs/auth-session-hardening-v3.9.1.md` (new)

## Notes

- `.local_secret` remains the JWT signing key; no key source changes were made.
- Public login/register request/response shapes were preserved.
- No frontend, parser, or CI changes were made in this task.
