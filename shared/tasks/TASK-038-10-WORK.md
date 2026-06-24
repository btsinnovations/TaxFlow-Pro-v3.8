# TASK-038.10 Local Auth System — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Complete the local-only auth system: master password + optional keyfile, Argon2/bcrypt, local sessions, no OAuth/network validation.

---

## Current state (pre-work done by orchestrator)

Scanned and read the following files:

- `backend/auth.py` — main auth helpers: `boot_local_admin`, `authenticate_local_user`, bcrypt password hashing, local JWT signing secret, server-side Session + RefreshToken management, logout/revocation.
- `backend/local/auth.py` — `LocalAuthManager` with bcrypt hashing, legacy SHA-3_256 migration, optional keyfile support, `LocalCryptoManager` integration.
- `backend/routers/auth.py` — `/auth/boot`, `/auth/login`, `/auth/login-json`, `/auth/refresh`, `/auth/change-password`, `/auth/me`, `/auth/logout`. Currently uses `backend/auth.py` helpers, not `LocalAuthManager`.
- `backend/local/crypto.py` — Argon2id key derivation, AES-256-GCM encryption, optional keyfile factor.
- `backend/schemas.py` — `UserCreate`, `LocalLogin`, `LocalBoot`, `TokenPair`, `User` schemas.
- `backend/models.py` — `User` model has `encryption_salt` and `keyfile_path` columns.
- `backend/tests/test_hybrid_auth.py` — extensive tests for boot/login/logout/refresh/change-password/brute-force.
- `backend/tests/test_local_first.py` — crypto + local auth + backup + offline tests.
- `backend/utils/password_policy.py` — master password entropy policy.
- `docs/TODO_FIRST.md` — marks 3.7 as in progress.

**Gap identified:** `backend/routers/auth.py` does not expose keyfile support. The `/auth/boot` endpoint accepts only a password; there is no way for a user to provide a keyfile during initial setup or login. `backend/local/auth.py` already implements keyfile logic, but it is isolated from the API layer.

---

## Jane's tasks

### 1. Add keyfile support to `/auth/boot`

Update `backend/routers/auth.py`:

- Extend `BootRequest` schema to accept an optional `keyfile_path: str | None = None`.
- Pass the keyfile path to `boot_local_admin`.
- Update `backend/auth.py` `boot_local_admin(db, master_password, keyfile_path=None)` to:
  - Accept an optional `keyfile_path: Optional[Path]`.
  - If provided, validate the file exists and is at least 32 bytes.
  - Store the resolved absolute path in `user.keyfile_path`.
  - Use `LocalCryptoManager.create(master_password, keyfile_path)` so the encryption salt is bound to the password+keyfile combo.

Return the user model as before; no breaking change to the response shape.

### 2. Add keyfile support to `/auth/login` and `/auth/login-json`

- Extend `LoginRequest` and the OAuth2 form flow to accept an optional `keyfile_path`.
- In login, after password verification, if the user has a stored `keyfile_path` but none was supplied, reject with 401 + clear message.
- If a keyfile is supplied, resolve it and compare to the stored path (or accept it if the user has no keyfile configured, for migration edge cases).
- On successful login, call `register_column_crypto_manager(user.id, password, user.encryption_salt, keyfile_path)` so column encryption works with the keyfile factor.

### 3. Add `/auth/register-local` (optional but recommended)

If `backend/local/auth.py` `LocalAuthManager` is the canonical local implementation, expose a single-admin registration endpoint that uses it. However, the existing `/auth/boot` already covers first-boot setup. **Decision:** do not add `/auth/register-local` unless it simplifies the keyfile story. Instead, ensure `/auth/boot` is the single entry point.

### 4. Update `backend/auth.py` `authenticate_local_user`

- Accept optional `keyfile_path: Optional[Path] = None`.
- After password verification, if `user.keyfile_path` is set, validate the provided keyfile matches.
- Register the column crypto manager with the keyfile factor.

### 5. Add/update tests

Add tests to `backend/tests/test_hybrid_auth.py` or `backend/tests/test_local_auth.py`:

- `test_boot_with_keyfile_stores_path_and_allows_login`
  - Boot with password + keyfile.
  - Verify `user.keyfile_path` is set.
  - Login with password only → 401.
  - Login with password + keyfile → 200.
  - `/api/auth/me` works with the resulting token.

- `test_login_without_keyfile_after_keyfile_configured_fails`
  - Boot with keyfile.
  - Login without keyfile → 401 with clear detail.

- `test_change_password_keeps_keyfile_binding`
  - Boot with keyfile, login, change password, login again with new password + same keyfile.

- `test_keyfile_mismatch_rejected`
  - Boot with keyfile A, attempt login with keyfile B → 401.

### 6. Update `docs/TODO_FIRST.md`

Mark Phase 3 Gap **3.7 Local user/auth system** as ✅ complete.

### 7. Update `CHANGES.md`

Add a new section after Section 34: **Section 35 — Complete Local Auth System (TASK-038.10 / 3.7)** documenting:
- Files changed: `backend/auth.py`, `backend/routers/auth.py`, `backend/schemas.py`.
- Files added: `backend/tests/test_local_auth.py` (if new file) or tests added to `test_hybrid_auth.py`.
- Behavior: optional keyfile factor during boot/login, keyfile mismatch rejection, password change preserves keyfile binding.
- Verification commands and expected pass counts.

### 8. Run full tests and report

```bash
python -m pytest backend/tests/test_hybrid_auth.py -q
python -m pytest backend/tests/test_local_first.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

Report pass/fail counts.

---

## Implementation notes

### Keyfile validation helper

Add to `backend/local/crypto.py` or reuse:

```python
def validate_keyfile(path: Path) -> None:
    if not path.exists():
        raise EncryptionError(f"Keyfile not found: {path}")
    data = path.read_bytes()
    if len(data) < 32:
        raise EncryptionError("Keyfile must be at least 32 bytes")
```

Already present inside `_build_keyfile_key`; consider exposing a public helper.

### Schema changes

In `backend/schemas.py`, update existing classes rather than creating new ones to keep the API minimal:

```python
class LocalBoot(BaseModel):
    password: str
    keyfile_path: Optional[str] = None

class LocalLogin(BaseModel):
    username: str
    password: str
    keyfile_path: Optional[str] = None
```

`OAuth2PasswordRequestForm` does not natively support extra fields. For form login, accept keyfile via a separate query/body field or require JSON login (`/auth/login-json`) for keyfile flows. Recommended:
- `/auth/login` (form) stays password-only; if the user has a keyfile, return 401 with detail "Keyfile required; use /auth/login-json".
- `/auth/login-json` accepts `keyfile_path`.

Alternatively, add `keyfile_path: str | None = None` as a FastAPI dependency query param on `/auth/login`.

### No OAuth/network

Ensure the implementation does not add any OAuth provider, email verification, or external API call. The existing local secret + bcrypt + optional keyfile satisfies the requirement.

---

## Constraints

- Do not change `backend/local/auth.py` core logic unless necessary; prefer wiring it into the router.
- Do not remove `/auth/register` backdoor used by v3.7 tests.
- Do not restart gateway or modify OpenClaw config.
- Keep all changes local-first / no network.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- Updated `backend/auth.py` (keyfile-aware `boot_local_admin`, `authenticate_local_user`).
- Updated `backend/routers/auth.py` (keyfile-aware `/auth/boot`, `/auth/login`, `/auth/login-json`).
- Updated `backend/schemas.py` (optional `keyfile_path` on boot/login schemas).
- Updated `backend/tests/test_hybrid_auth.py` or new `backend/tests/test_local_auth.py`.
- Updated `docs/TODO_FIRST.md`.
- Updated `CHANGES.md` Section 35.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
