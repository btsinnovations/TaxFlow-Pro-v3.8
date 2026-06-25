# TASK-3.10.T05 — itsdangerous Signed Tokens

**Owner:** TBD  
**Goal:** Replace opaque `secrets.token_urlsafe()` session tokens with signed, timestamped, tamper-evident tokens.

## Files

- `backend/local/tokens.py` — new
- `backend/routers/auth.py`
- `backend/dependencies.py`
- `backend/tests/test_signed_tokens.py`

## Requirements

1. Use `itsdangerous.URLSafeTimedSerializer` with app secret key.
2. Tokens carry user_id, profile_id, issued_at, optional expiry.
3. Verify signature and expiry on every protected request.
4. Support token invalidation via a local blocklist or version rotation.

## Tests

- Valid token returns identity.
- Tampered token rejected.
- Expired token rejected.
- Logout invalidates token.

## Report

Files changed, token format, invalidation strategy.
