---

# TaxFlow Pro v3.11.0 — Chart of Accounts + Foundation Start

## Release summary (in progress)

- Scaffolded the v3.11 bookkeeping foundation beginning with module 3.11.01 (Chart of Accounts).
- Reused the existing `GLAccount` table for backward compatibility with v3.10 data.
- Added the first v3.11 UI shell route and backend/frontend wiring.

---

## Section 56 — v3.11 COA Scaffold (3.11.01)

**Files changed:**
- `backend/accounting/coa.py` (new)
- `backend/routers/coa.py`
- `backend/schemas.py`
- `backend/tests/test_coa.py` (new)
- `frontend/src/components/accounts/COATree.tsx` (new)
- `frontend/src/components/v3.11/index.ts`
- `frontend/src/App.tsx`
- `backend/models.py`
- `backend/local/roles.py`

**Files added:**
- `backend/accounting/coa.py`
- `backend/tests/test_coa.py`
- `frontend/src/components/accounts/COATree.tsx`

**Changes:**
- Added `backend/accounting/coa.py` domain module:
  - `AccountType` enum with the five canonical classes: `asset`, `liability`, `equity`, `income`, `expense`.
  - CRUD helpers `get_accounts`, `create_account`, `update_account`, `delete_account`.
  - Duplicate-code guard within a tenant.
  - Delete guard against accounts referenced by `transactions.gl_account_id`, `general_ledger_entries` debit/credit columns, or `categorization_rules.gl_account_id`.
  - Reuses the existing `GLAccount` table so v3.10 data remains intact.
- Updated `backend/routers/coa.py` with implemented FastAPI routes:
  - `GET /api/coa`
  - `POST /api/coa`
  - `PUT /api/coa/{id}`
  - `DELETE /api/coa/{id}`
  - Uses `get_current_user`, respects single/multi-tenant `X-Tenant-ID` handling, and returns the v3.11 COA wire shape.
- Updated `backend/schemas.py` `COAAccountType` enum values to lower-case strings (`asset`, `liability`, `equity`, `income`, `expense`) so they serialize directly to the database column format.
- Added `frontend/src/components/accounts/COATree.tsx`:
  - Wrapped in `ModuleShell` with `moduleId="3.11.01"`.
  - Table grid showing account `number`, `name`, `type` (colored badge), and `balance` placeholder.
  - Loads from `GET /api/coa` with skeleton, error, and empty states.
- Added `/chart-of-accounts` route to `frontend/src/App.tsx`.
- Added `COATree` re-export from `frontend/src/components/v3.11/index.ts`.
- Fixed `backend/models.py` `ProfileMembership` relationship declaration and `backend/local/roles.py` alias so the v3.11.02 roles module resolves against the canonical model without double-defining the table.

**Verification:**
```bash
python -m pytest backend/tests/test_coa.py -q
```
Expected: **13 passed, 0 failed**.

---

# TaxFlow Pro v3.10.0 — Desktop Packaging Release

## Release summary

- Packaged TaxFlow Pro as a single-user, offline-first desktop application.
- Built PyInstaller one-dir bundle (`dist/TaxFlowPro/`) for Windows.
- Added `scripts/taxflow_launcher.py` to resolve OS-specific local data directories, run Alembic migrations, wire vendored binaries, and start Uvicorn + browser.
- Vendored Tesseract OCR and Poppler PDF tools so no system installs are required.
- Provided Windows installer script (`scripts/installer_windows.iss`) for Inno Setup 6.
- Provided Linux AppImage/tarball build script (`scripts/build_linux.py`).
- Provided macOS `.app` + DMG build script (`scripts/build_macos.py`).
- Updated static frontend serving in `backend/api.py` with SPA fallback for browser routes.
- Bumped version to `3.10.0` across `version.txt`, `frontend/package.json`, and `pyproject.toml`.

## Section 50 — Local Data Directory + Launcher

**Files changed:**
- `scripts/taxflow_launcher.py`
- `backend/local/settings.py` (verified it respects `TAXFLOW_LOCAL_ROOT`)

**Changes:**
- Launcher resolves per-OS user data directory:
  - Windows: `%LOCALAPPDATA%\TaxFlowPro`
  - macOS: `~/Library/Application Support/TaxFlowPro`
  - Linux: `~/.local/share/TaxFlowPro`
- Ensures `db/`, `backups/`, `uploads/`, `ml/`, `logs/` subdirectories.
- Sets `DATABASE_URL` to local SQLite, `ALEMBIC_CONFIG` to bundled `alembic.ini`, and runs `alembic upgrade head`.
- Wires `TESSERACT_CMD`, `TESSDATA_PREFIX`, and `POPPLER_PATH` from `vendored/`.
- Starts Uvicorn on `127.0.0.1:8000` and opens default browser.

**Verification:**
```powershell
$env:TAXFLOW_LOCAL_ROOT='C:\tmp\taxflow-test'
$env:TAXFLOW_NO_BROWSER='true'
$env:TAXFLOW_PORT='8002'
python scripts/taxflow_launcher.py
```
Expected: `http://127.0.0.1:8002/api/health` returns `200` with `version: 3.10.0`.

## Section 51 — Vendored Binaries

**Files changed:**
- `scripts/vendor_binaries.py`
- `vendored/tesseract/`
- `vendored/poppler/`
- `docs/VENDORED_BINS.md`

**Changes:**
- Vendor Poppler portable Windows zip into `vendored/poppler/`.
- Vendor Tesseract Windows NSIS installer into `vendored/tesseract/` (falls back to manual copy if UAC blocks silent install).
- Documented vendoring process, UAC caveat, and manual fallback.

## Section 52 — Static Frontend Serving

**Files changed:**
- `backend/api.py`

**Changes:**
- Mount `StaticFiles` at `/assets` for built frontend assets.
- Add `_SPAFallbackMiddleware` to return `frontend/dist/index.html` for non-API, non-asset browser routes.
- Preserves `/api/*` and `/health` routes.

## Section 53 — Windows PyInstaller Bundle + Installer

**Files changed:**
- `scripts/build_windows.py`
- `scripts/installer_windows.iss`
- `TaxFlowPro.spec` (PyInstaller generated spec)
- `dist/TaxFlowPro/`

**Changes:**
- `build_windows.py` runs `npm run build`, validates vendored binaries, and invokes PyInstaller with `alembic/`, `alembic.ini`, `frontend/dist`, and `vendored/` as bundled data.
- `installer_windows.iss` creates a per-user installer with Start Menu shortcut and optional desktop icon.
- Installer title/headers customized to "TaxFlow Pro Installer".

## Section 54 — Linux AppImage / Tarball

**Files changed:**
- `scripts/build_linux.py`
- `scripts/taxflow_launcher.py` (already cross-platform)

**Status:** Scaffolded. Build script produces portable tarball and AppImage recipe.

## Section 55 — macOS `.app` + DMG

**Files changed:**
- `scripts/build_macos.py`
- `scripts/Info.plist`

**Status:** Scaffolded. Build script produces `.app` bundle and `.dmg` image.

---

# TaxFlow Pro v3.9.2 — Security Sprint + Phase 3 Foundation Completion

## Release summary

- Completed TASK-036 through TASK-039 (Security Sprint).
- Completed all 14 Phase 3 Foundation sub-tasks (TASK-038.1 through TASK-038.14).
- Hardened test suite, fixed single-user default, closed entropy audit, and migrated to a centralized safe YAML loader.
- Fixed regression failures caused by missing `secrets` import, strict audit triggers, `encryption_salt=None` test fixtures, and version-string mismatches.
- Refactored `backend/tests/conftest.py` to guarantee a clean schema per test and resolve brute-force tracker carryover.
- Final test results: **442 passed, 1 skipped, 0 failed** (`backend/tests` + `tests/`).

---

## Section 41 — YAML Safe Loading (TASK-039)

**Files changed:**
- `backend/local/yaml_safe.py` (already present and complete)
- `phase3_pipeline/categorizer.py`
- `phase3_pipeline/category_loader.py`
- `phase3_pipeline/profile_manager.py`
- `backend/tests/test_yaml_safety.py`
- `.pre-commit-config.yaml`

**Changes:**
- Finalized `backend/local/yaml_safe.py`:
  - Uses `CSafeLoader` when available, `SafeLoader` otherwise.
  - Exposes `safe_load_yaml(text)`, `safe_load_yaml_file(path)`, and `YAMLError`.
  - Converts `yaml.YAMLError` into project-specific `YAMLError`.
  - Raises `YAMLError` when the requested file does not exist.
- Replaced `yaml.safe_load` with `safe_load_yaml_file` in:
  - `phase3_pipeline/categorizer.py::PriorityCategorizer.load_rules`
  - `phase3_pipeline/category_loader.py::CategoryLoader._load`
  - `phase3_pipeline/profile_manager.py::ProfileManager._load`
- Updated `backend/tests/test_yaml_safety.py` to remove TODOs and add real assertions:
  - Simple mapping parse (`foo: bar`, list).
  - `!!python/object` payload is rejected with `YAMLError`.
  - Missing file raises `YAMLError`.
  - AST scan bans unsafe `yaml.load(...)` calls without an explicit `Loader` and bans `yaml.unsafe_load`/`yaml.full_load`.
  - Verifies `phase3_pipeline` modules import `safe_load_yaml_file` and no longer import `yaml` or call `yaml.safe_load`.
- Added `yaml-safe-scan` pre-commit hook in `.pre-commit-config.yaml` that runs `python -m pytest backend/tests/test_yaml_safety.py -q` on every commit.
- Updated `docs/TODO_FIRST.md` item 3.12 as complete (YAML safe-load hardening).

**Why:** `yaml.safe_load` is acceptable, but centralizing on `backend.local.yaml_safe` ensures a single, auditable safe-loader policy. Explicit rejection of `!!python/object` tags prevents deserialization attacks via project configuration files (`categories.yaml`, `profiles.yaml`).

**Verification:**
```bash
python -m pytest backend/tests/test_yaml_safety.py -q
```
Expected: **5 passed, 0 failed**.

---

## Section 40 — Weak-Entropy Audit (TASK-038-Entropy-Audit)

**Files changed:**
- `backend/tests/test_entropy_audit.py`
- `backend/local/security_random.py` (already present, verified in use)

**Changes:**
- Audited `backend/`, `backend/routers/`, `backend/local/`, `phase3_pipeline/`, `scripts/`, and `tests/` for any `import random` or `from random import` statements.
- Confirmed no stdlib `random` usage exists in security-critical modules.
- Confirmed all tokens, salts, nonces, session identifiers, keyfile contents, and encryption keys use `secrets.token_*`, `secrets.token_bytes`, or `secrets.choice`:
  - `backend/auth.py` uses `secrets.token_urlsafe` for JWT `jti`, refresh tokens, and access-token session binding.
  - `backend/local/auth.py` uses `secrets.token_urlsafe` for opaque session tokens.
  - `backend/local/crypto.py` uses `secrets.token_bytes` for salts, nonces, keyfiles, and local secret keys.
  - `backend/local/sqlcipher_engine.py` uses `secrets.token_bytes` for SQLCipher salt, keyfiles, and keyring tokens.
  - `backend/routers/auth.py` uses `secrets.token_bytes` for new-user `encryption_salt`.
  - `backend/tests/conftest.py` uses `secrets.token_bytes` for test-user `encryption_salt`.
- Replaced `os.urandom` usage in `backend/crypto/backup_crypto.py` with `secrets.token_bytes(SALT_LEN)` for backup salt generation, keeping the entropy source CSPRNG-consistent with the rest of the codebase.
- Updated `backend/tests/test_entropy_audit.py` to remove TODOs and add real assertions:
  - Security modules never import `random`.
  - Security modules use `secrets` for tokens/keys/nonces.
  - No insecure `random.*` callables (`randint`, `choice`, `shuffle`, `sample`, `seed`) in security modules.
  - `secure_token`, `secure_urlsafe_token`, `secure_random_int`, `secure_alphanumeric` behave correctly.
  - `backend.local.security_random` itself uses `secrets`, not `random`.
- Documented completion in `docs/TODO_FIRST.md` item 3.10a.

**Why:** The stdlib `random` module is deterministic and predictable; any use for security-sensitive values (tokens, keys, salts, nonces) would compromise local encryption, session integrity, and keyfile generation. This audit enforces that the codebase only uses `secrets` for those values.

**Verification:**
```bash
python -m pytest backend/tests/test_entropy_audit.py -q
```
Expected: **all tests pass**.

---

## Section 39 — Simplify Single-User Default (TASK-038.14 / 3.11)

**Files changed:**
- `backend/local/settings.py`
- `backend/rls.py`
- `backend/api.py`
- `backend/routers/accounts.py`
- `backend/routers/clients.py`
- `backend/routers/depreciation.py`
- `backend/routers/flags.py`
- `backend/routers/gl.py`
- `backend/routers/rules.py`
- `backend/routers/tax.py`
- `backend/routers/transactions.py`
- `backend/routers/upload.py`
- `backend/routers/health.py`

**Files added:**
- `backend/tests/test_single_user_mode.py`

**Changes:**
- Added `TAXFLOW_SINGLE_USER` env flag defaulting to `true` and `is_single_user()` helper in `backend/local/settings.py`.
- Made `is_single_user()` read the env var dynamically so tests can toggle the mode without module reloads.
- Updated `backend/rls.py::get_current_tenant` to infer the tenant from the authenticated user's primary client in single-user mode, bypassing the `X-Tenant-ID` header requirement.
- Hardened `backend/api.py::rls_tenant_middleware` to reject multi-entity PostgreSQL requests that omit `X-Tenant-ID` or provide a non-numeric value, returning clear 400 messages.
- Updated strict `X-Tenant-ID` header checks across routers to only enforce the header in multi-entity PostgreSQL mode (`TAXFLOW_SINGLE_USER=false`).
- Added `backend/tests/test_single_user_mode.py` verifying default single-user mode, header-less SQLite requests, ignored arbitrary `X-Tenant-ID` header, and multi-entity header requirement under monkeypatched PostgreSQL mode.
- Ensured `/health`, `/api/health`, and `/api/health/config` report `single_user` and `multi_entity` runtime flags.

**Migration note:** Existing multi-entity PostgreSQL installs must set `TAXFLOW_SINGLE_USER=false` after upgrading to retain header-based tenant routing.

**Verification:**
```bash
python -m pytest backend/tests/test_single_user_mode.py -q
```
Expected: **5 passed, 0 failed**.

---

# TaxFlow Pro v3.9.1 — Patch Release Change Log

## Summary

This release hardens the local-first authentication layer, improves parser coverage, makes OCR a first-class opt-in parser, cleans up frontend placeholder data, and adds release discipline (CI/CD, pre-commit hooks, version hygiene). It builds on the v3.7 backend fixes, parser unification, PostgreSQL RLS, and local-first modules introduced in earlier phases.

---

## Section 38 — Hardened Test Suite (TASK-038.13 / 3.10)

**Files changed:**
- `backend/tests/test_crypto.py` (new)
- `backend/tests/test_pdf_fuzz.py` (new)
- `backend/tests/test_keyring_secret.py` (new)
- `backend/tests/test_local_first.py`
- `backend/tests/test_recovery.py`

**Changes:**
- Added `backend/tests/test_crypto.py` with focused local-encryption tests:
  - AES-256-GCM roundtrip and authentication-tag verification.
  - Tampered ciphertext rejects with `AuthenticationError`/`EncryptionError`.
  - Keyfile-factor independence: password-only vs. keyfile-bound ciphertexts cannot cross-decrypt.
  - Salt uniqueness, `from_stored()` reproduction, weak-input resilience, envelope-version validation.
- Added `backend/tests/test_pdf_fuzz.py` for parser guard/fuzz coverage:
  - Synthetic oversized PDF rejected by size limit.
  - Synthetic multi-page PDF rejected by page limit.
  - PDFs containing `/JavaScript`, `/EmbeddedFile`, and `/Launch` actions rejected by `pdf_guard`.
  - `backend.parsers.sandbox_entry` importability and invalid-payload error paths.
- Added `backend/tests/test_keyring_secret.py` for local secret file hardening:
  - Plaintext fallback is written inside `LOCAL_ROOT`.
  - POSIX secret file mode is `0o600`.
  - Windows secret file ACL excludes non-owner read access when pywin32 is available.
- Extended `backend/tests/test_local_first.py` with property-based and offline/security assertions:
  - Case-insensitive categorization determinism.
  - Description redaction/masking.
  - Deterministic `txn_uid` generation and amount-change sensitivity.
  - Default `FEATURE_FLAGS` all `False`.
  - `guard_cloud_call` blocks every configured feature key.
  - Default uvicorn bind is `127.0.0.1` unless `TAXFLOW_BIND_LAN` is set.
  - `run_bootstrap()` does not open non-loopback sockets.
- Extended `backend/tests/test_recovery.py` with recovery stress tests:
  - Concurrent read transaction during `auto_backup_after_import` remains consistent.
  - Repeated auto-backups produce distinct manifests and archive filenames.
  - `X-Tenant-ID` nonsense header is ignored in SQLite mode.

**Why:** The local-first stack needs deterministic, property-based, and adversarial tests that exercise crypto, parser guards, recovery, and offline guards without relying on the full integration suite. These tests close the hardened-test-suite gap and provide regression coverage for permission, sandbox, and local-only behavior.

**Verification:**
```bash
python -m pytest backend/tests/test_crypto.py -q
python -m pytest backend/tests/test_local_first.py -q
python -m pytest backend/tests/test_pdf_fuzz.py -q
python -m pytest backend/tests/test_keyring_secret.py -q
python -m pytest backend/tests/test_recovery.py -q
```
Expected: all targeted test files pass.

---

## Section 38 — Hardened Test Suite (TASK-038.13 / 3.10)

**Files changed:**
- `backend/tests/test_crypto.py` (new)
- `backend/tests/test_pdf_fuzz.py` (new)
- `backend/tests/test_keyring_secret.py` (new)
- `backend/tests/test_local_first.py`
- `backend/tests/test_recovery.py`

**Changes:**
- Added `backend/tests/test_crypto.py` with focused local-encryption tests:
  - AES-256-GCM roundtrip and authentication-tag verification.
  - Tampered ciphertext rejects with `AuthenticationError`/`EncryptionError`.
  - Keyfile-factor independence: password-only vs. keyfile-bound ciphertexts cannot cross-decrypt.
  - Salt uniqueness, `from_stored()` reproduction, weak-input resilience, envelope-version validation.
- Added `backend/tests/test_pdf_fuzz.py` for parser guard/fuzz coverage:
  - Synthetic oversized PDF rejected by size limit.
  - Synthetic multi-page PDF rejected by page limit.
  - PDFs containing `/JavaScript`, `/EmbeddedFile`, and `/Launch` actions rejected by `pdf_guard`.
  - `backend.parsers.sandbox_entry` importability and invalid-payload error paths.
- Added `backend/tests/test_keyring_secret.py` for local secret file hardening:
  - Plaintext fallback is written inside `LOCAL_ROOT`.
  - POSIX secret file mode is `0o600`.
  - Windows secret file ACL excludes non-owner read access when pywin32 is available.
- Extended `backend/tests/test_local_first.py` with property-based and offline/security assertions:
  - Case-insensitive categorization determinism.
  - Description redaction/masking.
  - Deterministic `txn_uid` generation and amount-change sensitivity.
  - Default `FEATURE_FLAGS` all `False`.
  - `guard_cloud_call` blocks every configured feature key.
  - Default uvicorn bind is `127.0.0.1` unless `TAXFLOW_BIND_LAN` is set.
  - `run_bootstrap()` does not open non-loopback sockets.
- Extended `backend/tests/test_recovery.py` with recovery stress tests:
  - Concurrent read transaction during `auto_backup_after_import` remains consistent.
  - Repeated auto-backups produce distinct manifests and archive filenames.
  - `X-Tenant-ID` nonsense header is ignored in SQLite mode.

**Why:** The local-first stack needs deterministic, property-based, and adversarial tests that exercise crypto, parser guards, recovery, and offline guards without relying on the full integration suite. These tests close the hardened-test-suite gap and provide regression coverage for permission, sandbox, and local-only behavior.

**Verification:**
```bash
python -m pytest backend/tests/test_crypto.py -q
python -m pytest backend/tests/test_local_first.py -q
python -m pytest backend/tests/test_pdf_fuzz.py -q
python -m pytest backend/tests/test_keyring_secret.py -q
python -m pytest backend/tests/test_recovery.py -q
```
Expected: all targeted test files pass.

---

## 13. Merchant Alias Matching Configuration (TASK-036 / Phase 1 Gap 1.3)

**Files changed:** `phase3_pipeline/categorizer.py`, `categories.yaml`, `tests/test_parsers.py`, `tests/test_aliases.yaml`

**Changes:**
- Added a top-level `alias_matching` configuration block to `categories.yaml`:
  - `default_mode: strict` — match aliases from the start of the description and truncate trailing store/location tokens (e.g., `WAL-MART #123` → `WALMART`).
  - `overrides` — per-canonical-merchant `mode: substring` to opt specific merchants out of strict truncation when substring replacement is safer (e.g., `PAYPAL`, `SQUARE`, `GOOGLE`).
- Updated `phase3_pipeline/categorizer.py`:
  - Reads `alias_matching.default_mode` and `alias_matching.overrides` at load time.
  - Compiles each alias as a start-anchored regex in `strict` mode or as a plain substring regex in `substring` mode.
  - Only applies `substring` aliases during the fallback replacement pass; strict aliases are already handled by the start-match pass.
- Updated `tests/test_aliases.yaml` with the new config block and `PAYPAL` overrides.
- Updated `tests/test_parsers.py::test_alias_normalization_with_fixture` to assert both strict truncation (`WAL-MART #123` → `WALMART`) and substring override behavior (`XYZ PAYPAL TRANSFER` → `XYZ PAYPAL`).

**Why:** The original start-of-string alias match was hardcoded and risked over-truncating descriptions for merchants whose tokens can appear anywhere. Making the behavior configurable per merchant lets the system keep strict canonicalization for most retailers while preserving substring normalization for payment processors and marketplaces.

**Verification:**
```bash
python -m pytest tests/test_parsers.py -v
```
Expected: **1 passed, 0 failed**.

---

## 14. Path Traversal Protection (TASK-033)

**Files changed:** `backend/security/path_safety.py`, `backend/api_utils.py`, `backend/routers/upload.py`, `backend/routers/export.py`, `scripts/backup.py`, `scripts/restore.py`, `backend/tests/test_path_traversal.py`, `.env.example`, `README.md`

**Changes:**
- Added `backend/security/path_safety.py` with:
  - `sanitize_filename(name)` — strips path separators, null bytes, control chars, shell metacharacters, reserved Windows device names (CON, PRN, AUX, NUL, COM1–9, LPT1–9 and digit suffixes), leading dots, and collapses spaces to underscores.
  - `safe_path(base_dir, rel_path, must_exist=False)` — resolves `rel_path` strictly under `base_dir` and raises `ValueError` on traversal attempts, absolute paths, or symlink escapes.
  - `safe_user_filename(user_id, name)` — combines the user prefix with sanitized filename for upload temp files.
- Updated `backend/api_utils.py` to use `safe_user_filename` instead of the old naive `Path(...).replace(..)` approach.
- Updated `backend/routers/upload.py` to pass the uploaded filename through the sanitizer before filesystem storage while keeping the original name in the database.
- Updated `backend/routers/export.py` to sanitize the statement export `Content-Disposition` filename. Added `_statement_export_filename()` helper.
- Updated `scripts/backup.py` to validate `--target-dir` resolves within the project root using `safe_path`.
- Updated `scripts/restore.py` to validate `--backup-dir` and `--target-path` resolve within the project root using `safe_path`.
- Added `backend/tests/test_path_traversal.py` with 30 tests covering:
  - Valid filename sanitization and acceptance.
  - `../etc/passwd` and nested traversal rejected by `safe_path`.
  - `file/../../etc/passwd` rejected.
  - `CON1.txt` and other reserved Windows names rejected.
  - Absolute paths rejected.
  - `must_exist` behavior.
  - User-scoped filename sanitization.
  - Upload temp file uses sanitized name.
  - Export filename sanitized.
- Updated `.env.example` with `TAXFLOW_EXPORT_DIR` default.
- Updated `README.md` with a "Path Safety" section describing the sanitization and base-directory enforcement rules.

**Why:** Any endpoint that accepts user-derived filenames or paths is a potential path-traversal vector. Centralizing sanitization and strict base-directory resolution prevents writes or reads outside the intended project directories across uploads, exports, backups, and restores.

**Verification:**
```bash
python -m pytest backend/tests/test_path_traversal.py -v
```
Expected: **30 passed, 0 failed**.

---

## 15. Request Size Limits + Strict Validation (TASK-031)

**Files changed:** `backend/api.py`, `backend/security/request_validation.py`, `backend/tests/test_request_size_limits.py`, `README.md`, `.env.example`

**Changes:**
- Added `backend/security/request_validation.py` with `MAX_BODY_SIZE_BYTES` loaded from `TAXFLOW_MAX_BODY_SIZE_BYTES` (default 10 MiB) and a `human_size()` helper.
- Added `_RequestSizeLimitMiddleware` in `backend/api.py` that runs before route handlers and rejects non-upload request bodies that exceed the general body limit.
- The middleware strictly validates the `Content-Length` header:
  - Malformed or negative values receive **400 Bad Request** with `"Invalid Content-Length header"`.
  - Values greater than `MAX_BODY_SIZE_BYTES` receive **413 Payload Too Large** with a `Retry-After` header set to the limit in bytes.
- `POST /api/upload` remains exempt from the general body limit and continues to use the upload-specific validator in `backend/security/upload_validator.py` (default 32 MiB).
- Added `backend/tests/test_request_size_limits.py` covering:
  - Small JSON request succeeds.
  - Oversized JSON body rejected by `Content-Length`.
  - Upload route exempt from the general limit.
  - Missing `Content-Length` passes through.
  - Invalid and negative `Content-Length` rejected with 400.
  - Zero `Content-Length` allowed.
  - End-to-end integration test with `TestClient` confirming 413 + `Retry-After`.
- Updated `README.md` and `.env.example` to document `TAXFLOW_MAX_BODY_SIZE_BYTES`.

**Why:** Without a general body-size cap, JSON endpoints could be pressured by very large request bodies. Strict validation of `Content-Length` prevents clients from bypassing the check with malformed headers and gives API consumers a clear, machine-readable error.

**Verification:**
```bash
python -m pytest backend/tests/test_request_size_limits.py -v
```
Expected: **8 passed, 0 failed**.

---

## 16. Server-Side Token Revocation (P0.2)

**Files changed:** `backend/auth.py`, `backend/models.py`, `backend/routers/auth.py`, `backend/tests/test_hybrid_auth.py`, `alembic/versions/1116e8143fc6_add_revoked_tokens_table.py`

**Changes:**
- Added a unique `jti` claim to every JWT issued by `create_access_token()`.
- Added a `RevokedToken` model (`revoked_tokens` table) with `jti`, `user_id`, `token_type`, `expires_at`, and `revoked_at`.
- Added Alembic migration `1116e8143fc6` to create the table, resolving the prior multi-head state by depending on the latest head `d2e3f4a5b6c7`.
- `decode_access_token()` now accepts an optional `db` session and rejects revoked tokens.
- `backend/routers/auth.py` `/api/auth/logout` now stores the current token's `jti` server-side instead of only telling the client to forget it.
- `_get_current_user()` passes its database session to `decode_access_token()`, so revocation is enforced on every protected route.
- Added 5 tests in `backend/tests/test_hybrid_auth.py`: `jti` presence, logout revokes token, revoked token is rejected, fresh login after logout, and double-logout returns 401.

**Why:** A local app with a 7-day JWT needs a way to invalidate sessions before expiry. Server-side revocation lets users log out confidently and gives the backend a lever for forced session termination (e.g., after password change or `.local_secret` rotation).

**Verification:**
```bash
python -m pytest backend/tests/ tests/ -q
```
Expected: **136 passed, 0 failed**.

---

## 17. Database-at-Rest Encryption (P0.1)

**Files changed:** `backend/auth.py`, `backend/routers/auth.py`, `backend/routers/clients.py`, `backend/routers/accounts.py`, `backend/routers/upload.py`, `backend/routers/transactions.py`, `backend/local/crypto.py`, `backend/local/column_encryption.py` (new), `backend/tests/test_encryption.py` (new)

**Changes:**
- Rejected SQLCipher for v3.9.1 after a feasibility spike: `pysqlcipher3` fails to build on Windows/Python 3.14, and wiring `sqlcipher3` into SQLAlchemy + Alembic exceeds patch-release risk.
- Pivoted to application-level column encryption using the existing `backend/local/crypto.LocalCryptoManager` (AES-256-GCM, Argon2id key derivation).
- Added `backend/local/column_encryption.py` helpers `encrypt_for_user()` / `decrypt_for_user()` and runtime cache helpers in `backend/local/crypto.py` (`register_column_crypto_manager`, `get_column_crypto_manager`, `clear_column_crypto_manager`).
- `backend/auth.py`: `boot_local_admin()` and `authenticate_local_user()` generate or reuse `users.encryption_salt` and cache the derived column manager.
- `backend/routers/auth.py`: `/api/auth/logout` clears the cached column manager.
- Encrypted columns at the router boundary:
  - `clients.tax_id`
  - `accounts.account_number_masked`
  - `transactions.description`
  - `statements.filename`
- Plaintext legacy values remain readable via no-op fallback in `decrypt_for_user()`.
- Added 6 encryption tests covering salt creation, `tax_id` round-trip, `account_number_masked` round-trip, ciphertext storage, logout manager clearing, and legacy/plaintext fallback.

**Why:** The local SQLite database file (`taxflow.db`) must not leak sensitive PII/financial data if accessed without the user's master password. Encrypting these columns means a stolen DB file is unusable unless both the password and the stored salt are present.

**Decision record:** `shared/decisions/2026-06-20-v3.9.1-encryption-decision.md`

**Verification:**
```bash
python -m pytest backend/tests/ tests/ -q
```
Expected: **142 passed, 0 failed**.

---

## 18. OCR Parser as First-Class Optional Build Item (P1.2)

**Files changed:** `backend/parsers/ocr_parser.py` (new), `backend/parsers/__init__.py`, `backend/parsers/institution.py`, `backend/routers/upload.py`, `frontend/src/sections/UploadSection.tsx`, `frontend/src/hooks/useAPI.ts`, `backend/tests/test_ocr_parser.py` (new)

**Changes:**
- Added `backend/parsers/ocr_parser.py` with a standalone `OCRPDFParser` class.
  - Configurable `language`, `dpi`, and `grayscale` preprocessing toggle.
  - Returns `GenericPDFParser`-compatible dict shape (`meta`, `reconciliation`, `transactions`, `pages`, `template`).
  - `OCRPDFParser.supported()` returns True only when `pdf2image`, `pytesseract`, and the Tesseract CLI are available.
  - Constructor raises a clear `RuntimeError` with install instructions when OCR is unavailable.
- Exported `OCRPDFParser` from `backend/parsers/__init__.py`.
- Added `parse_statement_pdf()` helper in `backend/parsers/institution.py` that routes to `OCRPDFParser` when `parse_options["force_ocr"]` is True; otherwise uses `GenericPDFParser`.
- `backend/routers/upload.py`: `POST /api/upload/` now accepts an optional `force_ocr` form field and passes it through `parse_options`. Backward-compatible for clients that omit the field.
- Frontend:
  - `frontend/src/hooks/useAPI.ts`: `uploadFile()` accepts an optional `forceOcr` boolean and appends it to the FormData.
  - `frontend/src/sections/UploadSection.tsx`: added a "Use OCR" switch in the Options card; the selected value is sent only for PDF uploads.
- Added `backend/tests/test_ocr_parser.py` covering:
  - `supported()` returns a bool.
  - Constructor raises `RuntimeError` when OCR is unavailable.
  - Import-missing graceful degradation path.
  - Functional mocked round-trip producing non-empty OCR text.
  - Grayscale preprocessing toggle.

**Why:** The previous OCR path was a silent fallback inside `GenericPDFParser` only triggered when extracted text was < 200 characters. Users with known scanned statements need an explicit, testable, optional parser they can choose at upload time.

**Constraints respected:**
- The silent OCR fallback in `GenericPDFParser` is preserved.
- OCR is not the default.
- Heavy image preprocessing is only enabled by the `grayscale` toggle.

**Verification:**
```bash
python -m pytest backend/tests/ tests/ -q
```
Expected: **all tests pass**. OCR tests will skip or assert bool-only behavior if Tesseract/Poppler are not installed.

---

## 19. Parser Coverage Expansion (P1.1)

**Files changed:** `backend/parsers/institution.py`, `backend/parsers/parser_base.py` (new), `backend/parsers/tdbank.py` (new), `backend/parsers/chime.py` (new), `backend/parsers/edfed.py` (new), `backend/parsers/queensborough.py` (new), `backend/parsers/__init__.py`, `backend/parsers/generic_pdf.py`, `backend/parsers/transaction_builder.py` (indirectly via shape), `backend/routers/upload.py`, `backend/tests/test_parser_regression.py` (new)

**Changes:**
- Added a shared helper module `backend/parsers/parser_base.py` with reusable functions for date parsing, amount extraction, signed-amount normalization, and the canonical `GenericPDFParser.parse()` output shape (`build_parse_result`).
- Expanded institution detection in `backend/parsers/institution.py`:
  - TD Bank credit card keywords (`td bank credit`, `td cash`, `td first class`, `td business credit`).
  - Chime checking keywords (`chime checking`, `spending account`).
  - EdFed credit keywords (`edfed rewards visa`, `edfed credit card`, `educational federal credit union credit`).
  - Queensborough National Bank & Trust detection (`queensborough national bank`, `queensborough bank & trust`, `qnb`).
  - Restored `Cash App` to the detection registry.
- Added institution-specific parsers that dispatch ahead of the generic template pipeline:
  - `backend/parsers/tdbank.py` — TD Bank checking (MM/DD Description Amount) and credit card (MM/DD/YYYY Description Amount).
  - `backend/parsers/chime.py` — Chime checking and Credit Builder single-column layouts.
  - `backend/parsers/edfed.py` — EdFed share draft (with continuation-line merging) and Rewards Visa credit.
  - `backend/parsers/queensborough.py` — simple Date/Description/Amount layout.
- Updated `backend/parsers/institution.py` `parse_statement_pdf()` to:
  - Dispatch to institution-specific parsers when a known institution is detected.
  - Return a `needs_review: true` result (empty transactions, null template) for unknown institutions when `force_ocr` is False.
  - Set `needs_review: true` on OCR-first results.
- Updated `backend/parsers/generic_pdf.py` to include `needs_review: false` in its output for shape consistency.
- Exported new parsers from `backend/parsers/__init__.py`.
- Updated `backend/routers/upload.py` to surface `needs_review` and a warning in the upload response when the parser flags the statement for review.
- Added `backend/tests/test_parser_regression.py` exercising synthetic fixtures for TD Bank (checking + credit), Chime (checking + Credit Builder), EdFed (share draft + credit), BofA, Chase, BECU, Queensborough, and an unknown-institution fallback.

**Why:** Several high-volume institutions (TD Bank credit, Chime checking, EdFed credit, Queensborough) were either undetected or unsupported, forcing all their statements through the generic template parser where they often produced zero transactions. Institution-specific parsers give users usable extraction and a clear flag when a statement still needs manual review.

**Constraints respected:**
- No changes to existing parser tests in `test_parser_unification.py` or `test_institution_detection.py`.
- Output shape remains compatible with `GenericPDFParser.parse()`.
- Synthetic PDF fixtures generated with `fpdf`; no real statements used.
- Generic template parser remains the fallback for known institutions without a specific parser (e.g., BofA, Chase, BECU).

**Verification:**
```bash
python -m pytest backend/tests/ tests/ -q
```
Expected: **all tests pass**.

---

## 20. Frontend Mock-Data Cleanup (P1.3)

**Files changed:** `frontend/src/sections/MLTraining.tsx`, `frontend/src/sections/TaxRules.tsx`, `frontend/src/sections/TestSuite.tsx`, `frontend/src/components/LoginModal.tsx`, `frontend/src/data/mockData.ts`, `frontend/src/hooks/useAPI.ts`, `frontend/src/context/AuthContext.tsx`, `frontend/src/context/ToastContext.tsx`, `frontend/src/sections/ExportFormats.tsx`, `frontend/src/sections/UploadSection.tsx`, `frontend/vite.config.ts`, `backend/routers/tax.py`, `backend/routers/tests.py`

**Changes:**
- Replaced static `mlCategoryMetrics` and `modelVersions` imports in `MLTraining.tsx` with a `useEffect` call to `getMLStatus()`.
- Added `loading`, `error`, and empty states to `MLTraining.tsx`.
- Wired the "Train Now" button to `runTests()` as a proxy for training.
- Wired the "Incremental Training" toggle to `toggleML()` and refresh status.
- Replaced static `taxRules` import in `TaxRules.tsx` with a `useEffect` call to `getTaxRules()`.
- Added loading skeleton and error state to `TaxRules.tsx`; detail panel safely handles a `null` selected rule.
- Replaced static `testResults` import in `TestSuite.tsx` with a `useEffect` call to `getTests()`.
- Added "Run All Tests / Run Parsers Only / Run ML Tests / Run Tax Rules" buttons that call `runTests()`.
- Added loading skeleton and error state to `TestSuite.tsx`; results normalized from either an array or raw pytest output.
- Removed the "Create Account" / registration mode toggle in `LoginModal.tsx`; only boot and login modes remain.
- Added the dev-only comment at the top of `frontend/src/data/mockData.ts` and kept the file for storybook/tests.
- Updated `useAPI.ts` `getTaxRules()` and `updateTaxRule()` to pass a required `tenant_id` query parameter.
- Updated `backend/routers/tax.py` to provide `GET /api/tax/` and `PATCH /api/tax/{rule_id}` endpoints returning categorization rules.
- Updated `backend/routers/tests.py` `GET /api/tests/` to return a stable shape and `POST /api/tests/run` to include `elapsed` timing.
- Fixed pre-existing TypeScript strict errors in `AuthContext.tsx`, `ToastContext.tsx`, `ExportFormats.tsx`, and `UploadSection.tsx` so `tsc -b` passes.
- Raised frontend build chunk-size warning limit so the production build completes cleanly.

**Why:** `MLTraining`, `TaxRules`, and `TestSuite` were rendering hard-coded mock data, which misrepresented real system health. Wiring them to live endpoints and adding skeleton/error/empty states gives users accurate feedback.

**Verification:**
```bash
python -m pytest backend/tests/ tests/ -q
npm run build --prefix frontend
```
Expected: **backend all tests pass; frontend build passes**.

---


## 21. Security Cleanup (SEC-02 + SEC-03)

**Files changed:** `backend/routers/auth.py`, `backend/utils/password_policy.py`, `backend/utils/redaction.py`, `backend/audit/audit_trail.py`, `backend/models.py`, `backend/tests/test_hybrid_auth.py`, `backend/tests/test_redaction.py`, `backend/tests/conftest.py`, `alembic/versions/2227f9254a8b_add_audit_description_and_redaction_support.py`

**Changes:**
- Added `backend/utils/password_policy.py` with master-password entropy enforcement: minimum length 12, minimum estimated entropy 50 bits, rejects literal `'password'`, rejects username substring, rejects a common-password set.
- Enforced the policy on `/api/auth/boot`, `/api/auth/register`, and `/api/auth/change-password`. Login flow behavior remains unchanged so existing users are not locked out.
- Added `backend/utils/redaction.py` with `redact_pii()` and `redact_pii_in_json()` helpers for SSN/TIN (dashed and 9-digit), 16-digit card numbers, bank account numbers >6 digits, email addresses, and US phone numbers.
- Applied redaction to the `description` field and recursively to all string values in the `details` JSON blob of every audit entry before DB insert, preserving JSON structure and chain integrity.
- Added `description` column to `audit_entries` via Alembic migration `2227f9254a8b`.
- Added `backend/tests/test_redaction.py` covering all PII patterns and JSON nesting.
- Updated existing auth and encryption tests to use strong master passwords that satisfy the new policy.

**Why:** Weak boot/registration passwords and PII in audit logs were the two highest-severity gaps in the v3.9.1 security audit. These changes close them without breaking existing sessions or the tamper-evident audit chain.

**Verification:**
```bash
python -m alembic upgrade head
python -m pytest backend/tests/ tests/ -q
```
Expected: **all tests pass**, Alembic at `2227f9254a8b (head)`.

\n## 21. Data Integrity (DATA-01 + DATA-02)

**Files changed:** backend/local/backup.py, backend/local/migration_health.py, scripts/backup.py, scripts/restore.py, backend/routers/health.py, backend/api.py, backend/tests/test_backup_restore.py, backend/tests/test_migration_health.py

**Changes:**
- Added backup_db(db_path, target_dir) and 
estore_db(backup_dir, target_path) helpers in backend/local/backup.py that copy a SQLite database alongside a manifest.json containing a SHA-256 hash and timestamp.
- Added scripts/backup.py and scripts/restore.py CLI entry points for one-command database backup and hash-verified restore.
- Added backend/local/migration_health.py exposing check_migrations(db_url) using Alembic ScriptDirectory and MigrationContext.
- Wired migration health check into backend/api.py startup: logs a warning if pending migrations exist; exits with SystemExit(1) when STRICT_MIGRATIONS=true.
- Added backend/routers/health.py with authenticated GET /api/health/migrations and public GET /api/health/public endpoints.
- Added backend/tests/test_backup_restore.py covering manifest creation, successful restore, and tamper detection failure.
- Added backend/tests/test_migration_health.py covering fresh DB at head and stale revision with pending migrations.

**Why:** Automated, verifiable backups and deterministic migration health reporting are required for a production-ready local-first deployment. These deliverables close DATA-01 and DATA-02 from the v3.9.1 security/data-integrity audit.

**Verification:**
`bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
python scripts/backup.py --target-dir C:\\tmp\\tf-backup-test --db-path taxflow.db
python scripts/restore.py --backup-dir C:\\tmp\\tf-backup-test --target-path C:\\tmp\\tf-restored.db
python -m pytest backend/tests/ tests/ -q
`
Expected: backup and restore scripts print paths; **all tests pass**.


## 22. CI/CD + Version Hygiene (P2.1 + P2.2)

**Files changed:** `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `requirements.txt`, `requirements-dev.txt`, `version.txt`, `README.md`, `docs/frontend-smoke-test.md`, `frontend/package.json`, `backend/api.py`, `backend/routers/health.py`, `backend/tests/test_api.py`

**Changes:**
- Added `.github/workflows/ci.yml` with two jobs:
  - `test-backend`: runs on `ubuntu-latest`/Python 3.11, installs `requirements.txt` + `requirements-dev.txt`, runs `pytest backend/tests/ tests/`, applies Alembic migrations, then installs Node 20 and builds the frontend.
  - `test-frontend`: runs on `ubuntu-latest`/Node 20, runs `npm ci` and `npm run build`; runs `npm run lint` only when the script exists.
- Added `.pre-commit-config.yaml` with `pre-commit-hooks`, `black --check`, `ruff --fix --exit-non-zero-on-fix`, and a local frontend build hook.
- Split dependencies:
  - `requirements.txt` now contains production packages only.
  - New `requirements-dev.txt` contains `pytest`, `pytest-asyncio`, `httpx`, `black`, `ruff`, `pre-commit`, `coverage`, `factory-boy`, and `faker`.
- Created `version.txt` at project root containing `3.9.1`.
- Updated `README.md` title and backend setup instructions to reference `requirements.txt` + `requirements-dev.txt`.
- Updated `docs/frontend-smoke-test.md` version header and prerequisites to mention dev requirements.
- Bumped `frontend/package.json` version from `0.0.0` to `3.9.1`.
- Updated `backend/api.py` and `backend/routers/health.py` to read the canonical version from `version.txt`; `/api/health/public` and both `/health` and `/api/health` endpoints return `3.9.1`.
- Updated `backend/tests/test_api.py` health assertions to expect `3.9.1`.

**Why:** Before release, the repo needs automated CI, deterministic formatting/linting, a clean split between production and development dependencies, and a single source of truth for the release version.

**Verification:**
```bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
cat version.txt
python -m pytest backend/tests/ tests/ -q
python -c "from backend.api import app; from fastapi.testclient import TestClient; print(TestClient(app).get('/api/health/public').json())"
```
Expected: `version.txt` = `3.9.1`; public health returns `{'status': 'ok', 'version': '3.9.1'}`; **all tests pass**.

## 23. Brute-Force Protection for Login (P0.1)

**Files changed:** `backend/auth_rate_limit.py` (new), `backend/routers/auth.py`, `backend/tests/test_hybrid_auth.py`

**Changes:**
- Added `backend/auth_rate_limit.py` with an in-memory per-username failed-attempt tracker.
  - Tracks `failed_attempts`, `last_attempt`, and `lockout_until`.
  - Progressive delay enforced via HTTP 429 and `Retry-After`: 1 s, 2 s, 4 s, 8 s, ...
  - Hard lockout after 10 consecutive failures until the application process restarts.
  - No state is persisted to disk.
- Decorated `POST /api/auth/login` and `POST /api/auth/login-json` with the rate-limit checks.
  - Calls `check_login_attempt(username)` before password verification.
  - Calls `record_login_failure(username)` on bad password.
  - Calls `record_login_success(username)` on successful login, resetting the counter.
- Kept login error messages generic ("Incorrect master password") so username enumeration remains impossible.
- Added 5 new tests in `backend/tests/test_hybrid_auth.py`:
  - Exponential `Retry-After` progression.
  - Lockout after 10 failures and rejection of correct password while locked out.
  - Successful login resets the failure counter.
  - Counter reset simulates an app restart.
  - Fresh Python process starts with an empty tracker.

**Why:** The master password is the single trust anchor for a local-first financial app. Unlimited online password attempts would let malware or a local attacker brute-force weak passwords quickly. In-memory progressive backoff and a hard lockout close that path without adding any disk persistence that could itself be attacked.

**Verification:**
```bash
python -m pytest backend/tests/test_hybrid_auth.py -q
python -m pytest backend/tests/ tests/ -q
```
Expected: brute-force tests pass; full suite remains green.

## 24. Local Server Bind by Default (3.4c)

**Files changed:** `backend/api.py`, `README.md`, `start.sh`

**Changes:**
- Added an `if __name__ == "__main__"` uvicorn startup block to `backend/api.py` that defaults to host `127.0.0.1` and port `8000`.
- LAN/opt-in binding via `TAXFLOW_BIND_LAN=true` or explicit `UVICORN_HOST`/`UVICORN_PORT` overrides.
- Updated `README.md` quick-start to show `--host 127.0.0.1` and noted the LAN opt-in flag.
- Updated `start.sh` to launch with `--host 127.0.0.1` and print the opt-in environment variable.

**Why:** Defaulting to `0.0.0.0` exposes the local API to the LAN, which is unnecessary for a single-user local-first app and increases attack surface.

**Verification:**
```bash
python -c "from backend.api import app; print('import ok')"
```

---

## 25. Fallback Secret File Hardening (3.4f)

**Files changed:** `backend/local/keyring_secret.py`

**Changes:**
- Resolved `.local_secret` under `LOCAL_ROOT` via `get_local_path(".local_secret")` instead of the current working directory.
- Kept `TAXFLOW_LOCAL_SECRET_FILE` env var override.
- Created parent directories on first write.
- Restricted file permissions to owner-only: POSIX `0o600`; Windows owner-only DACL using pywin32 where available.
- Fixed a Windows-only bug where `win32security.GetUserName()` was used instead of `win32api.GetUserName()`.

**Why:** The plaintext fallback for the JWT signing key must be as narrow as possible. Keeping it inside the configured local root and tightening ACLs reduces exposure when keyring is unavailable.

**Verification:**
```bash
python -c "from backend.api import app; print('import ok')"
python -m pytest backend/tests/test_hybrid_auth.py -q
```

---

## 26. Server-Side Session Validation (3.4g)

**Files changed:** `backend/models.py`, `backend/auth.py`, `backend/routers/auth.py`, `backend/tests/test_hybrid_auth.py`, `alembic/versions/53e636150d46_add_server_side_sessions.py`

**Changes:**
- Added a `Session` model (`sessions` table) with:
  - `token_hash` (SHA-256 of the full JWT, unique index)
  - `token_jti` (the JWT `jti` claim, indexed)
  - `user_id` (FK to `users.id`)
  - `expires_at`, `revoked_at`, `created_at`, `last_seen_at`, `ip_address`, `user_agent`
- `create_access_token()` now accepts an optional DB session and creates a `Session` row for every issued access token.
- `decode_access_token()` now accepts an optional DB session and rejects tokens whose `Session` row is missing, expired, or revoked.
- `rotate_refresh_token()` and all auth routes (`/boot`, `/login`, `/login-json`, `/refresh`) now bind new access tokens to a server-side session.
- `/api/auth/logout` marks both the `Session` row and the legacy `RevokedToken` record as revoked.
- Added 4 focused tests in `backend/tests/test_hybrid_auth.py`:
  - `test_access_token_creates_server_side_session`
  - `test_missing_session_rejects_valid_signature`
  - `test_session_revoked_on_logout`
  - `test_fresh_login_after_logout_creates_new_session`
- Added Alembic migration `53e636150d46` to create the `sessions` table as a clean child of `4f0bb0ee4bff`.

**Why:** JWT-only validation relies on signature checking and expiry, but it cannot invalidate a token server-side or detect a token that never came from this instance. The `Session` table binds each access token to a stored row, giving the backend explicit control over every active session.

**Verification:**
```bash
python -m alembic upgrade 53e636150d46
python -m pytest backend/tests/test_hybrid_auth.py -q
python -m pytest backend/tests -q
```
Expected: Alembic at `53e636150d46 (head)`; backend tests pass.

---


The remainder of this file documents the v3.7 backend fixes and validation work that v3.9.1 builds upon.

---

# TaxFlow Pro v3.7 — Backend Fixes and Validation

## Summary

This change set fixes the backend issues identified by the validator, removes dead code, aligns the backend with the frontend's API expectations, adds a new backend test suite, resolves the pre-existing pipeline test failures in the `phase3_pipeline` package, and implements Loop 1 (PostgreSQL + Alembic + tenant isolation) for the backend persistence layer.

---

## 1. Dependency Fixes (`requirements.txt`)

**Files changed:** `requirements.txt`

**Changes:**
- Added `joblib>=1.3.0` — required by `phase3_pipeline/ml_categorizer.py`.
- Added `scikit-learn>=1.4.0` — required by `phase3_pipeline/ml_categorizer.py` (TF-IDF + LogisticRegression pipeline).
- Added `pyyaml>=6.0.0` — required by `phase3_pipeline/categorizer.py` to load `categories.yaml`.
- Added `httpx>=0.27.0` — required by FastAPI `TestClient` for backend tests.
- Added `alembic>=1.13.0`, `psycopg2-binary>=2.9.0`, `python-dotenv>=1.0.0` — Loop 1 migration stack.

**Why:** The CLI import failed with `ModuleNotFoundError: joblib`, and the pipeline tests failed with `ModuleNotFoundError: yaml`. `httpx` is a transitive test dependency of FastAPI's `TestClient`. The new Alembic/Postgres dependencies support Loop 1.

---

## 2. CORS and API Prefix Alignment (`backend/api.py`)

**Files changed:** `backend/api.py`

**Changes:**
- Added `http://localhost:5173` and `http://127.0.0.1:5173` to `allow_origins` to support the Vite dev server.
- Added `prefix="/api"` to all `include_router(...)` calls so backend routes match the frontend's `useAPI.ts` base URL (`http://localhost:8000/api`).
- Added a second health endpoint at `/api/health` for clients that only call under `/api`.
- Replaced import-time `Base.metadata.create_all()` with `run_migrations()` using Alembic `command.upgrade(config, "head")`.
- Alembic `sqlalchemy.url` is set dynamically from `engine.url`.

**Why:** The frontend uses Vite (port 5173) and calls `/api/upload/`, `/api/clients/`, etc. The backend was exposing `/upload/`, `/clients/`, etc. directly and only allowed CORS from port 3000, causing blocked requests in the default dev setup. Loop 1 requires schema-managed migrations instead of `create_all()`.

---

## 3. Secret Key Externalization (`backend/routers/auth.py`)

**Files changed:** `backend/routers/auth.py`

**Changes:**
- Replaced hardcoded `SECRET_KEY` with `os.environ.get("TAXFLOW_SECRET_KEY", "taxflow-dev-secret-key-change-in-production-2026")`.
- Updated `oauth2_scheme` `tokenUrl` from `auth/login` to `/api/auth/login` to match the new global `/api` prefix.

**Why:** The hardcoded secret was a security risk for any deployment. The dev fallback remains for local development, but production must set `TAXFLOW_SECRET_KEY`.

---

## 4. Statement Period Extraction (`backend/parsers/generic_pdf.py`)

**Files changed:** `backend/parsers/generic_pdf.py`

**Changes:**
- Added `_extract_statement_period()` method that searches common statement labels ("Statement Period", "Period", "From ... To", "Statement Date") and parses dates into ISO format (`YYYY-MM-DD`).
- Merged the extracted `period_start` and `period_end` into the `meta` dict returned by `parse()`.

**Why:** `backend/routers/upload.py` was reading `period_start`/`period_end` from `result["meta"]`, but `GenericPDFParser.parse()` never returned them, so the `Statement` table always stored `None` for those columns. This caused the PDF summary export to show "N/A" for the period.

---

## 5. Dead Code Removal

**Files removed:**
- `backend/api_models.py` — contained duplicate Pydantic models not imported anywhere. `backend/schemas.py` is the active schema layer.
- `backend/api_utils.py` — implemented a JSON-file database (`api_db.json`) that no router used. All routers use `backend/database.py` (SQLAlchemy/SQLite).
- `config/settings.yaml` — not loaded by any module. Tax rules are managed elsewhere.
- `backend/__pycache__/api_utils.cpython-314.pyc` — stale compiled bytecode of removed file.

**Why:** Dead code confused maintenance and could be mistaken for active functionality. Removing it clarifies the architecture.

---

## 6. Missing API Endpoints Added for Frontend Compatibility

**Files changed:** `backend/routers/clients.py`, `backend/routers/accounts.py`, `backend/routers/export.py`, `backend/routers/ml.py`

**Changes:**
- `clients.py`: Added `PATCH /api/clients/{client_id}` for client updates.
- `accounts.py`: Added `client_id` query filter to `GET /api/accounts/` and added `PATCH /api/accounts/{account_id}` for account updates.
- `export.py`: Added `GET /api/export/formats` returning the supported export format list (CSV, JSON, QIF, QBO, Xero, Excel, PDF, Parquet).
- `ml.py`: Added `GET /api/ml/status` and `POST /api/ml/toggle` stubs that return deterministic responses when no ML model is trained.

**Why:** The frontend calls these endpoints in `useAPI.ts`, but they were missing or only partially implemented, causing 404 errors in the UI.

---

## 7. Backend Test Suite (`backend/tests/`)

**Files added:**
- `backend/tests/conftest.py` — Test database fixture with dependency override for `get_db`.
- `backend/tests/test_api.py` — Tests covering health endpoints, CORS, auth secret key env override, registration/login, protected routes, client CRUD, account CRUD, export formats, ML status, test runner, upload rejection of non-PDFs, and parser period extraction.

**Results:**
- `backend/tests/`: **13 passed, 0 failed**
- `tests/` (pipeline tests): **18 passed, 0 failed**

---

## 8. Pipeline Test Fixes (`phase3_pipeline/`)

**Files changed:** `phase3_pipeline/identity.py`, `phase3_pipeline/categorizer.py`, `categories.yaml`, `phase3_pipeline/graph.py`, `phase3_pipeline/invariants.py`, `phase3_pipeline/ml_categorizer.py`, `phase3_pipeline/normalization.py`, `tests/test_parsers.py`, `phase3_pipeline/config.py`

### 8.1 Identity UID stability (`phase3_pipeline/identity.py` + `phase3_pipeline/categorizer.py` + `categories.yaml`)

**Problem:** `IdentityService.generate()` uppercased and stripped the alias-normalized description but did not remove trailing store numbers or punctuation. Variants like `"WAL-MART #123"` and `"Walmart"` produced different UIDs. Similarly, `"Amazon Marketplace"` had no merchant alias.

**Fix:**
- `categorizer.PriorityCategorizer._apply_aliases()` now matches aliases from the start of the description and returns the canonical merchant name, discarding trailing location/store numbers. If no start-of-string alias matches, it falls back to the old substring replacement behavior.
- `IdentityService.generate()` now strips non-alphanumeric characters and collapses whitespace after alias normalization for an extra layer of canonicalization.
- Added `'AMAZON MARKETPLACE': 'AMAZON'` to `categories.yaml`.

### 8.2 Duplicate `txn_uid` validation (`phase3_pipeline/graph.py` + `tests/test_graph.py`)

**Problem:** `TransactionGraph.add()` raised `ValueError` immediately on duplicate `txn_uid`, but `tests/test_invariants.py` expected `validate(graph)` to detect duplicates. The graph behavior and the invariant test were inconsistent.

**Fix:**
- `TransactionGraph.add()` now records every transaction in `_all_nodes` while keeping the first occurrence in `nodes` for lookup. Duplicates are no longer rejected at insertion time.
- `TransactionGraph.all()`, `live()`, and `roots()` iterate over `_all_nodes` so invariants can detect duplicates.
- Updated `tests/test_graph.py::test_duplicate_raises` to `test_duplicate_stored_and_validated`, asserting that duplicates are stored and later caught by `validate()`.

### 8.3 ML fallback with missing model (`phase3_pipeline/ml_categorizer.py`)

**Problem:** `MLCategorizer` always loaded `PriorityCategorizer("categories.yaml")` using a path relative to the current working directory, which failed when tests ran from `tests/`. The monkeypatch test for a missing model also caused the categories file to appear missing, triggering an unhandled `FileNotFoundError`.

**Fix:**
- `MLCategorizer` now resolves `categories.yaml` relative to the module file (`phase3_pipeline` parent directory) with a fallback to the current working directory.
- Missing categories file is caught gracefully: ML is disabled and `priority_cat` is set to `None`. `predict()` returns `"Other:Uncategorized"` if the rule-based fallback is unavailable.

### 8.4 EU date normalization (`phase3_pipeline/normalization.py`)

**Problem:** `normalize_date("09.06.2026")` was passed to `dateutil`, which interpreted it as US format (`MM.DD.YYYY`) and returned `2026-09-06` instead of `2026-06-09`.

**Fix:** Added an explicit `DD.MM.YYYY` / `DD.MM.YY` regex handler before the `dateutil` path. Dot-separated numeric dates are now parsed as day-month-year when both day and month are valid.

### 8.5 Missing `Path` import (`tests/test_parsers.py`)

**Problem:** `test_alias_normalization_with_fixture` used `Path(__file__).parent / "test_aliases.yaml"` without importing `Path`.

**Fix:** Added `from pathlib import Path` to the test file.

### 8.6 Fuel tax classification (`phase3_pipeline/config.py`)

**Problem:** `classify_transaction("SHELL OIL")` returned `"uncategorized"` because `TAX_RULES` only contained `"fuel"` and `"gas"` keywords, neither of which matched the tokens in `"SHELL OIL"`.

**Fix:** Added fuel merchant keywords to `TAX_RULES`: `"shell oil"`, `"shell"`, `"chevron"`, `"exxon"`, `"mobil"`, `"marathon"`, `"speedway"`, `"bp"`. These rules use token-subset matching, so `"SHELL OIL"` now maps to `fuel_expense`.

---

## 9. Loop 1 — PostgreSQL + Alembic + Tenant Isolation

**Files changed:** `backend/database.py`, `backend/api.py`, `backend/models.py`, `backend/schemas.py`, `backend/routers/accounts.py`, `backend/routers/upload.py`, `backend/routers/export.py`, `backend/routers/tax.py`, `backend/routers/audit.py`, `backend/routers/dashboard.py`, `backend/routers/ml.py`, `requirements.txt`, `alembic.ini`, `alembic/env.py`

**Files added:** `alembic/versions/d75a7eba9fd0_baseline_schema.py`, `MIGRATIONS.md`

### 9.1 Database configuration (`backend/database.py`)
- Reads `DATABASE_URL` from root `.env` using `python-dotenv`.
- Defaults to `sqlite:///./taxflow.db` when the env var is unset.
- Uses SQLite-friendly `connect_args` for local/test mode.
- Uses `pool_size`, `max_overflow`, and `pool_timeout` tuned for PostgreSQL when the URL starts with `postgresql://`.

### 9.2 Model tenant isolation (`backend/models.py`)
- Added non-nullable `tenant_id` foreign key to `clients.id` on `Account`, `Statement`, and `Transaction`.
- Added `user_id` to `Statement` for direct ownership checks.
- Made `client_id` and `user_id` non-nullable on `Account`.
- Added per-table tenant indexes.
- Added explicit relationship definitions to resolve SQLAlchemy FK ambiguity.
- Tenant boundary is `client_id`: each business entity (client) is a separate tenant, so one user can manage multiple businesses.

### 9.3 Startup migration (`backend/api.py`)
- Replaced import-time `Base.metadata.create_all()` with `run_migrations()` that runs Alembic `command.upgrade(config, "head")`.
- Alembic `sqlalchemy.url` is set dynamically from `engine.url`.
- Migration runs once at startup. The dev/test default still uses SQLite.

### 9.4 Alembic setup
- Created `alembic.ini` and `alembic/env.py`.
- Generated baseline migration `d75a7eba9fd0_baseline_schema` that creates all tables with tenant columns, indexes, and foreign keys.
- Removed the earlier partial migration (`54c037c01035`) to keep history clean.

### 9.5 Schema updates (`backend/schemas.py`)
- `AccountCreate` requires `client_id`; `Account` exposes `tenant_id`.
- Added `AccountUpdate` and `ClientUpdate` for PATCH endpoints.
- `Statement` and `Transaction` schemas expose `tenant_id`.

### 9.6 Router tenant filtering
- `accounts.py`: `tenant_id` is derived from `client_id` on create and updated alongside it on PATCH. `GET /api/accounts/?client_id=...` filters by `client_id`/`tenant_id` and `user_id`.
- `upload.py`: newly created statements and transactions inherit `tenant_id` and `user_id` from the owning account.
- `export.py`, `tax.py`, `audit.py`, `dashboard.py`, `ml.py`: queries filter by `Statement.user_id` or `Transaction.tenant_id`.

### 9.7 Application-level isolation only
- Phase 1 does **not** implement PostgreSQL Row-Level Security (RLS). Tenant filtering is in the application layer so SQLite dev/tests keep working.
- RLS is deferred to a future production-PostgreSQL phase.

---
## 10. How to Validate

```bash
cd projects/TaxFlow-Pro-v3.7-main
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m pytest backend/tests/ -v
python -m pytest tests/ -v
python -m pytest tests/ backend/tests/ -v
```

Expected results:
- `backend/tests/`: 13 passed, 0 failed
- `tests/` (pipeline tests): 18 passed, 0 failed
- combined: 31 passed, 0 failed

---

## 11. Phase 2 — Parser Unification + PostgreSQL Row-Level Security

**Approved by Josh.**

### 12.1 Parser unification

**Files added/updated:**
- `backend/parsers/__init__.py` — exports canonical API.
- `backend/parsers/generic_pdf.py` — refactored to expose `parse_pdf_to_dict()` and `parse_pdf_to_transactions()`; legacy `GenericPDFParser` class preserved.
- `backend/parsers/institution.py` — shared institution detection (Cash App, TD, Chime, EdFed, etc.).
- `backend/parsers/transaction_builder.py` — dict ↔ DB model helpers, deduplication, tx_type inference.
- `phase3_pipeline/pdf_parser.py` — thin backward-compatible wrapper that delegates to `backend.parsers`.
- `phase3_pipeline/identity.py` — added `IdentityService.generate_stable()` alias used by plugin parser base.
- `backend/tests/test_parser_unification.py` — 9 tests covering both paths.

**Behavior:**
- `parse_pdf_to_dict(pdf_path)` returns the same dict shape the backend upload router expects (`template`, `account_info`, `transactions`, `reconciliation`, `meta`).
- `parse_pdf_to_transactions(pdf_path)` returns the transaction list for CLI/pipeline use.
- Institution-specific logic continues to live in the `phase3_pipeline/parsers` plugin registry, but the backend can detect common institutions and the pipeline wrapper falls back to the unified parser when no plugin matches.
- The pipeline wrapper re-adds the project root to `sys.path` so `backend.parsers` is importable from `phase3_pipeline/`.

### 12.2 PostgreSQL Row-Level Security (RLS)

**Files added/updated:**
- `backend/rls.py` — helpers: `is_postgres()`, `set_tenant_id()`, `clear_tenant_id()`, `TenantScope` context manager, `install_rls_event_listeners()`.
- `backend/database.py` — installs RLS event listeners on PostgreSQL; no change for SQLite.
- `backend/api.py` — `rls_tenant_middleware` reads `X-Tenant-ID` and stores it on `request.state`.
- `backend/routers/auth.py`, `clients.py`, `accounts.py`, `upload.py`, `export.py`, `dashboard.py`, `tax.py`, `ml.py`, `audit.py` — each DB session is wrapped with the tenant context when running on PostgreSQL.
- `alembic/versions/b9f4e2c8d310_enable_postgresql_row_level_security.py` — PostgreSQL-only migration that enables RLS and creates `current_setting('taxflow.tenant_id')` policies on `accounts`, `statements`, and `transactions`.
- `backend/tests/test_rls.py` — 7 tests validating helper behavior, middleware state, and migration shape.

**Design:**
- RLS is only active when `DATABASE_URL` starts with `postgresql://`.
- Each DB connection is initialized with an empty `taxflow.tenant_id` via `connect`/`checkout` event listeners.
- Routers call `set_tenant_id(db, tenant_id)` before querying when an `X-Tenant-ID` header is present.
- PostgreSQL policies use `taxflow.tenant_id_matches(tenant_id)`, which compares the row's `tenant_id` to `current_setting('taxflow.tenant_id', true)`.
- SQLite dev/tests are completely unaffected; `is_postgres()` returns `False`, and tenant helpers are no-ops.

### 12.3 Test results after Phase 2

```bash
python -m pytest backend/tests/ tests/ -v
```

- `backend/tests/`: **30 passed, 0 failed**
- `tests/` (pipeline tests): **18 passed, 0 failed**
- **Combined: 48 passed, 0 failed**

### 12.4 Blockers / follow-ups

- No blockers. PostgreSQL RLS enforcement is ready but requires a live PostgreSQL database to validate the policies end-to-end. SQLite coverage remains intact.

---
## 12. Phase 3 — Local-First Bulletproof Backend

**Decided by Josh (2026-06-14).**

**Goal:** Make TaxFlow Pro fully functional offline on the user's machine. Backend is the only priority for this phase; frontend updates are deferred.

### 13.1 Non-goals for this phase
- Stripe / Paddle / any billing
- Cloud sync, SaaS multi-tenant hosting
- Plaid / live bank feeds
- Mobile apps
- SOC 2 / external compliance audits

### 13.2 Core requirements
- **No internet required at runtime.** All models, OCR, parsing, and categorization run locally. No external API calls on startup or during processing. Graceful behavior when the network is unavailable.
- **Local-only data storage.** SQLite default for personal/small-biz tier; optional local PostgreSQL for heavier users. All data stays on disk the user controls. Encrypted at rest with a user-derived key (optional, not mandatory).
- **Self-contained installer/package.** One-click install on Windows, macOS, and Linux. Bundles Python runtime, Tesseract, Poppler, and frontend assets. No manual dependency hunting.
- **Offline model inference.** Categorizer trains and predicts locally. No cloud ML APIs. Model files are local artifacts the user owns.
- **Local authentication.** No OAuth / Google / email verification over the network. Master password + optional local keyfile. Session tokens generated locally; no external JWT validation.
- **Bulletproof reliability.** ACID transactions, automatic backups on every import, crash recovery / WAL mode SQLite, idempotent imports, validation invariants that reject corrupt data.

### 13.3 Architecture target
- Single-user-first local app. Multi-seat still possible on a local network if desired, but default install is one user, one encrypted SQLite database.
- `users` table becomes local identity, not a SaaS account.
- `clients` becomes "profile" or "business entity."
- Remove `X-Tenant-ID` middleware reliance for single-user mode; keep it as optional multi-entity mode.
- Authentication: local Argon2 password hash + optional keyfile.
- Encryption: SQLCipher-style layer or application-level encryption before writes.

### 13.4 Proposed module plan
```
backend/
  local/
    auth.py          # master password + keyfile auth
    crypto.py        # encrypt/decrypt data at rest
    backup.py        # local snapshot + restore
    bootstrap.py     # first-run setup, self-test
    offline.py       # network detection + graceful degradation
  models.py          # keep, simplify for single-user default
  api.py             # remove external middleware; local-only mode flag
  settings.py        # local config file instead of env vars where possible
```

### 13.5 Backend work items

| #  | Task | Why It Matters |
| -- | ---- | -------------- |
| 1 | Audit every external dependency | Replace or vendor anything that phones home |
| 2 | Add offline startup self-test | Detects missing Tesseract, models, or DB and reports locally |
| 3 | Implement local encryption layer | User master password derives key for data at rest |
| 4 | Make SQLite bulletproof | WAL mode, backups, idempotent imports, integrity checks |
| 5 | Remove or gate all cloud/API code | No Plaid, no SMTP, no telemetry, no update checks |
| 6 | Local model training pipeline | User can retrain categorizer on their own data |
| 7 | Local user/auth system | Master password, keyfile, local sessions |
| 8 | Local backup/restore/export | Encrypted snapshots the user controls |
| 9 | Graceful degradation specs | What works offline, what is disabled, clear messaging |
| 10 | Hardened test suite | Property-based tests, corruption tests, recovery tests |

### 13.6 Platform + packaging
- **Holy trinity roadmap:** Windows, macOS, and Linux.
- **Desktop wrapper vs browser + local server:** Chose **browser + local server** for now. The backend is already FastAPI/Vite React, LAN multi-seat is trivial, and the same bundle works on all three OSes. Wrappers (Electron/Tauri) add weight and update complexity; they can be explored later once the backend is bulletproof.

### 13.7 Open questions resolved
- Encryption: optional, not mandatory.
- Multi-seat: keep LAN multi-seat capability; default is single-user.
- OS roadmap: Windows, macOS, Linux.
- Desktop wrapper: deferred; browser + local server first.

---
## 13. Remaining Recommendations

- Unify the two PDF parsing paths: `backend/parsers/generic_pdf.py` (backend upload) and `phase3_pipeline/pdf_parser.py` (CLI pipeline) diverge in behavior and institution support.
- Add a `.env.example` file documenting `DATABASE_URL` and `TAXFLOW_SECRET_KEY` for production deployments.
- Implement PostgreSQL Row-Level Security (RLS) when moving to a dedicated production PostgreSQL instance.
- Consider whether the alias-start matching in `categorizer.py` should be configurable per merchant to avoid over-eager truncation.
- Add future schema changes as new Alembic migrations rather than editing the baseline migration once it has run in a shared environment.

---

# Appendix A — Historical v3.7 Backend Fixes and Validation

> This section preserves the original change log from `TaxFlow-Pro-v3.7`.
> It documents the dependency fixes, CORS/API-prefix alignment, statement period extraction,
> parser unification, Loop 1 (PostgreSQL + Alembic + tenant isolation), and Phase 2/3 planning
> that v3.9.1 builds upon. It is reproduced here so `TaxFlow-Pro-v3.9` remains the single,
> authoritative source of truth for the full project history.

## A.1 Summary

This change set fixes the backend issues identified by the validator, removes dead code, aligns the backend with the frontend's API expectations, adds a new backend test suite, resolves the pre-existing pipeline test failures in the `phase3_pipeline` package, and implements Loop 1 (PostgreSQL + Alembic + tenant isolation) for the backend persistence layer.

### A.1.1 Dependency Fixes (`requirements.txt`)

**Files changed:** `requirements.txt`

- Added `joblib>=1.3.0`, `scikit-learn>=1.4.0`, `pyyaml>=6.0.0`, `httpx>=0.27.0`.
- Added `alembic>=1.13.0`, `psycopg2-binary>=2.9.0`, `python-dotenv>=1.0.0` for Loop 1.

### A.1.2 CORS and API Prefix Alignment (`backend/api.py`)

- Added Vite origins (`http://localhost:5173`, `http://127.0.0.1:5173`).
- Added `prefix="/api"` to all routers.
- Added `/api/health`.
- Replaced `Base.metadata.create_all()` with Alembic `command.upgrade(config, "head")`.

### A.1.3 Secret Key Externalization (`backend/routers/auth.py`)

- Replaced hardcoded `SECRET_KEY` with `os.environ.get("TAXFLOW_SECRET_KEY", ...)`.
- Updated `tokenUrl` to `/api/auth/login`.

### A.1.4 Statement Period Extraction (`backend/parsers/generic_pdf.py`)

- Added `_extract_statement_period()` searching common statement labels and returning ISO `period_start` / `period_end`.

### A.1.5 Dead Code Removal

Removed `backend/api_models.py`, `backend/api_utils.py`, `config/settings.yaml`, and stale `__pycache__`.

### A.1.6 Missing API Endpoints Added

- `PATCH /api/clients/{client_id}`
- `GET /api/accounts/?client_id=...` + `PATCH /api/accounts/{account_id}`
- `GET /api/export/formats`
- `GET /api/ml/status` + `POST /api/ml/toggle`

### A.1.7 Backend Test Suite

- Added `backend/tests/conftest.py` and `backend/tests/test_api.py`.
- Initial result: `backend/tests/` 13 passed; `tests/` 18 passed.

### A.1.8 Pipeline Test Fixes

- UID stability via start-of-string alias matching and trailing-store stripping.
- Duplicate `txn_uid` caught by `validate()` rather than on insertion.
- ML fallback resolves `categories.yaml` relative to module and disables gracefully if missing.
- EU date normalization for `DD.MM.YYYY` / `DD.MM.YY`.
- Added missing `from pathlib import Path`.
- Added fuel merchant keywords to `TAX_RULES`.

## A.2 Loop 1 — PostgreSQL + Alembic + Tenant Isolation

**Files changed:** `backend/database.py`, `backend/api.py`, `backend/models.py`, `backend/schemas.py`, backend routers, `requirements.txt`, `alembic.ini`, `alembic/env.py`.
**Files added:** `alembic/versions/d75a7eba9fd0_baseline_schema.py`, `MIGRATIONS.md`.

- `database.py`: reads `DATABASE_URL` from `.env`; defaults to SQLite; PostgreSQL pool settings.
- `models.py`: non-nullable `tenant_id` FK on `Account`, `Statement`, `Transaction`; `user_id` on `Statement`; explicit relationships.
- `api.py`: Alembic `upgrade head` at startup; dynamic `sqlalchemy.url`.
- `schemas.py`: `AccountCreate` requires `client_id`; added `AccountUpdate`/`ClientUpdate`.
- Routers: tenant-aware filtering.
- No PostgreSQL RLS in this phase; application-level isolation only to preserve SQLite dev/tests.

## A.3 Phase 2 — Parser Unification + PostgreSQL Row-Level Security

- `backend/parsers/` canonical API and `phase3_pipeline/pdf_parser.py` backward-compatible wrapper.
- `backend/rls.py` with `set_tenant_id`, `TenantScope`, and PostgreSQL-only policies.
- PostgreSQL RLS migration `b9f4e2c8d310`.
- Test results after Phase 2: `backend/tests/` 30 passed, `tests/` 18 passed.

## A.4 Phase 3 — Local-First Bulletproof Backend

**Decided by Josh (2026-06-14).** Goal: fully functional offline on the user's machine. Non-goals included billing, cloud sync, Plaid, mobile apps, and external compliance audits. Core requirements: no internet at runtime, local SQLite default with optional local PostgreSQL, self-contained installer, offline ML inference, local master-password auth, ACID + WAL + automatic backups. Platform target: Windows, macOS, Linux via browser + local server first; desktop wrappers deferred.

## 27. SQLCipher Database-at-Rest Encryption + Encrypted Backup/Restore (TASK-038)

**Files changed:** `backend/database.py`, `backend/local/settings.py`, `backend/local/backup.py`, `requirements.txt`

**Files added:** `backend/local/sqlcipher_engine.py`, `backend/tests/test_sqlcipher_engine.py`, `docs/ENCRYPTION.md`

**Changes:**
- Added `backend/local/sqlcipher_engine.py` with:
  - Argon2id master-password key derivation to a 256-bit raw SQLCipher key.
  - Random per-database salt stored in a public sidecar (`<db>.salt`).
  - Optional keyfile and OS-keyring token mixing as second factors.
  - `create_sqlcipher_engine()` factory using `module=sqlcipher3.dbapi2`.
  - `migrate_plaintext_to_sqlcipher()` helper.
  - `rekey_sqlcipher_database()` helper.
  - `generate_keyfile()` / `generate_keyring_token()` helpers.
- Wired SQLCipher into `backend/database.py`: `DATABASE_URL=sqlcipher:///...` routes to the SQLCipher engine; plain `sqlite://` and `postgresql://` paths remain unchanged.
- Added SQLCipher settings/env vars in `backend/local/settings.py`:
  - `TAXFLOW_DB_PASSWORD`
  - `TAXFLOW_DB_KEYFILE`
  - `TAXFLOW_DB_KEYRING_TOKEN`
- Updated `backend/local/backup.py` to be SQLCipher-aware:
  - `backup_db()` detects SQLCipher DBs via the salt sidecar and copies `<db>.salt` into the backup directory; manifest records `sqlcipher: true`.
  - `restore_db()` restores the encrypted database, then copies the salt sidecar back so the key can be re-derived on open.
  - `is_sqlcipher_database()` tightened to require both a salt sidecar and a non-SQLite header.
- Added `docs/ENCRYPTION.md` documenting threat model, configuration, key lifecycle, migration, backup considerations, and remaining production decisions for Josh / btsinnovations.
- Added 6 SQLCipher engine tests in `backend/tests/test_sqlcipher_engine.py`:
  - PRAGMA key literal round-trip.
  - Wrong-password open fails.
  - Plaintext-to-SQLCipher migration preserves data.
  - Rekeying preserves data.
  - Keyfile as a second factor.
  - Missing keyfile rejects open.
- Added 2 SQLCipher backup tests in `backend/tests/test_backup_restore.py`:
  - SQLCipher detection heuristic.
  - SQLCipher backup/restore round-trip including salt sidecar restoration and data verification.
- Added `sqlcipher3-wheels` to `requirements.txt`.

**Why:** Requirement 3.3 and 3.8 from the local-first plan require a local encryption layer and encrypted backup/restore. SQLCipher keeps the SQLite database encrypted at rest while remaining API-compatible with SQLAlchemy. The backup layer copies the encrypted bytes plus the public salt sidecar, so backups are fully encrypted, portable, and recoverable on the same machine with the same master password.

**Verification:**
```bash
python -m pytest backend/tests/test_sqlcipher_engine.py backend/tests/test_backup_restore.py -v
```
Expected: **15 passed, 5 warnings, 0 failed**.

Full backend regression:
```bash
python -m pytest backend/tests -q
```
Expected: **340 passed, 97 warnings, 0 failed**.

**Production decisions remaining:**
- How the master password is captured on first run and whether a keyfile/OS-keyring factor is required.
- Offline recovery procedures when the password is lost (no backdoor is implemented by design).
- Whether SQLCipher should become the default for new installs or remain opt-in via `DATABASE_URL`.

---

## 28. Idempotent Transaction Import Contract (TASK-038.5 / Phase 3 Gap 3.4a)

**Files changed:** `phase3_pipeline/identity.py`, `backend/models.py`, `backend/routers/upload.py`

**Files added:** `alembic/versions/35b27f93b50d_add_txn_uid_and_import_source.py`, `backend/tests/test_idempotent_upload.py`

**Changes:**
- Extended `phase3_pipeline/identity.py`:
  - Added `IdentityService.generate_transaction_uid()` which produces a deterministic `txn_uid` from:
    - `TXN_VERSION` prefix for key evolution
    - Institution (uppercase, stripped)
    - Account label (uppercase, stripped)
    - Date
    - Canonicalized amount (two-decimal string, currency symbols/whitespace stripped)
    - Canonicalized description (`normalize_alias` + punctuation collapse + store/location normalization)
  - `generate_transaction_uid()` returns a SHA-256 hex digest of the joined normalized fields.
- Added `backend/routers/upload.py::_upsert_transactions()`:
  - Computes `txn_uid` for each parsed row before insert.
  - Queries existing rows by `(tenant_id, user_id, txn_uid)`.
  - On conflict, updates the existing row's `statement_id`, `date`, `description`, `amount`, `tx_type`, `running_balance`, and sets `import_source = "upload_upsert"`.
  - On first import, inserts a new row with `import_source = "upload"`.
- Updated `backend/models.py`:
  - Added `txn_uid` and `import_source` columns to `Transaction`.
  - Added unique composite index `ix_transactions_txn_uid` on `(tenant_id, user_id, txn_uid)`.
- Added Alembic migration `35b27f93b50d_add_txn_uid_and_import_source.py` to create the new columns and index.
- Added `backend/tests/test_idempotent_upload.py` with 5 tests:
  - `test_identity_transaction_uid_is_deterministic` — verifies similar inputs converge.
  - `test_identity_transaction_uid_distinguishes_inputs` — verifies amount/date/description/account changes produce different UIDs.
  - `test_upsert_creates_transactions_on_first_import` — first upload inserts rows.
  - `test_upsert_does_not_duplicate_on_reimport` — re-upload of the same row updates, does not duplicate.
  - `test_upsert_updates_amount_on_changed_source_row` — a changed row (different date/amount) creates a second distinct transaction.
- Fixed `backend/tests/test_migration_health.py` to discover the current Alembic head dynamically rather than hardcoding it, preventing the test from breaking on every new migration.

**Why:** Duplicate transactions are a common data-integrity failure when users re-upload statements or sync retries fire. A deterministic UID plus upsert guarantees idempotent imports without requiring a fragile external correlation ID.

**Verification:**
```bash
python -m pytest backend/tests/test_idempotent_upload.py backend/tests/test_migration_health.py -v
```
Expected: **7 passed, 0 failed**.

**Production decisions remaining:**
- Whether changed-but-similar rows (e.g., same description/institution/account but different amount or date) should be treated as the same transaction or a new one. Current design treats date or amount changes as new transactions, preserving the original source-of-truth.
- Whether to expose `txn_uid` to users or keep it internal.
- How to handle historical duplicates already present in a database before this migration is applied.

---

## 29. PII/PCI Masking for Audit Logs and Exports (TASK-038.3 / Phase 3 Gap 3.4b)

**Files changed:** `backend/routers/audit.py`, `backend/routers/export.py`, `backend/services/export.py`, `backend/local/guards.py`

**Files added:** `backend/utils/redaction.py`, `backend/tests/test_redaction.py`

**Changes:**
- Added `backend/utils/redaction.py` with redaction helpers:
  - `mask_account_number(value)` — masks digits to last 4 (or fully masks if ≤4 digits).
  - `redact_description(value)` — replaces a raw sensitive description with `[REDACTED]`.
  - `redact_text(value)` — generic full-text redaction.
  - `mask_transaction_description(value)` — keeps descriptions readable while scrubbing 9+ digit runs that look like account/card numbers.
  - `redact_pii(value)` and `redact_pii_in_json(payload)` — recursive redaction for audit details; masks account/card/routing/tax keys and scrubs description/memo fields.
- Updated `backend/audit/audit_trail.py` (existing usage) to keep using `redact_pii` / `redact_pii_in_json` from the new module, ensuring signed audit entries never contain raw sensitive strings.
- Updated `backend/routers/audit.py`:
  - Added `_redact_audit_entries()` that masks `account_number`, `card_number`, `routing_number`, `tax_id`, and fully redacts `description` fields inside returned `AuditEntryOut.details`.
- Updated `backend/services/export.py`:
  - Added `_mask_text_fields()` helper that masks CSV columns by header heuristic (`account`, `card`, `routing`, `tax_id`) and scrubs 9+ digit runs in `description` / `memo` columns.
  - Wired `_mask_text_fields()` into `export_transactions()` and `export_general_ledger()` so bulk CSV exports redact PII by default.
- Updated `backend/routers/export.py`:
  - Applied `mask_transaction_description()` to transaction descriptions in all statement export formats (`json`, `csv`, `qbo`, `xero`, `excel`, `parquet`, `qif`).
  - PDF summary already aggregates by category, so no raw descriptions are exposed; no change needed.
- Updated `backend/local/guards.py`:
  - Added `redact_sensitive_values(payload)` convenience wrapper for audit/export metadata surfaces.
- Added `backend/tests/test_redaction.py` with 10 tests:
  - Account/card number masking.
  - Short/non-digit passthrough.
  - Description/text redaction.
  - Transaction description digit scrubbing.
  - Sensitive value dict redaction.
  - CSV export column masking via `_mask_text_fields`.

**Why:** Requirement 3.4b requires that exports and audit artifacts not leak full account numbers or sensitive raw descriptions. The DB retains full source data; masking happens only at output/audit surfaces.

**Verification:**
```bash
python -m pytest backend/tests/test_redaction.py backend/tests/test_idempotent_upload.py backend/tests/test_migration_health.py -v
```
Expected: **16 passed, 0 failed**.

**Production decisions remaining:**
- Whether to mask account numbers in the UI Account list view or keep them masked there as well.
- Whether tax IDs (SSN/EIN) should be fully redacted or masked to last 4 in different contexts.
- Whether to add a user toggle for "include full descriptions in exports" (opt-in, default off).

---

## 30. PDF Parser Sandbox Hardening (TASK-038.4 / Phase 3 Gap 3.4e)

**Files changed:** `backend/routers/upload.py`, `backend/parsers/sandbox_entry.py`, `backend/parsers/generic_pdf.py`, `backend/parsers/ocr_parser.py`, `backend/parsers/institution.py`, `backend/local/guards.py`

**Files added:** `backend/parsers/pdf_guard.py`

**Tests extended:** `backend/tests/test_parser_sandbox.py`

**Changes:**
- Added `backend/parsers/pdf_guard.py` with fast byte-level PDF safety checks (no parser library imports required):
  - File size limit (default 32 MiB; configurable via `max_size_bytes`).
  - Page count limit (default 100 pages; uses `/Type /Pages /Count N` and `/Type /Page` heuristics).
  - Rejection of PDFs containing `/JavaScript`, `/JS`, `/Launch`, `/SubmitForm`, `/ImportData`, `/URI`, `/EmbeddedFile`, `/RichMedia`, `/AA`, or `/OpenAction` paired with any forbidden action.
  - Detection of obfuscated executable streams when suspicious filters are combined with forbidden actions.
- Wired `pdf_guard` checks:
  - `backend/routers/upload.py` calls `inspect_pdf()` on the validated bytes before writing to disk or invoking the sandbox.
  - `backend/parsers/sandbox_entry.py` re-runs the guard inside the subprocess before importing parser libraries (defense-in-depth).
  - `backend/parsers/institution.py` calls `validate_pdf_safety()` before dispatching to institution-specific or generic parsers.
  - `backend/parsers/generic_pdf.py` enforces `max_pages` in `extract_text()` and the OCR fallback path.
  - `backend/parsers/ocr_parser.py` enforces `max_pages` when converting pages to images.
- Replaced the duplicate PyPDF2-based guard in `backend/local/guards.py` with a thin wrapper that re-exports `pdf_guard` helpers and provides `validate_pdf_safety()` and a `PDFSecurityError` alias.
- Extended `backend/tests/test_parser_sandbox.py` with tests for:
  - Valid fpdf-generated PDF passes guard.
  - Embedded JavaScript PDF rejected by guard and by sandbox.
  - Oversized PDF rejected.
  - Excessive page count rejected.

**Why:** Requirement 3.4e requires that malicious or malformed PDFs cannot exploit the parser or hang the host. Running a lightweight byte-level guard in the parent process plus the sandbox entry point blocks oversized, multi-page, or action-bearing PDFs before heavy parser libraries are loaded.

**Verification:**
```bash
python -m pytest backend/tests/test_parser_sandbox.py backend/tests/test_redaction.py backend/tests/test_idempotent_upload.py backend/tests/test_migration_health.py -v
```
Expected: **26 passed, 0 failed**.

**Production decisions remaining:**
- Whether to allow users to override `max_pages` or `max_file_size_bytes` via settings.
- Whether to quarantine rejected uploads for forensic review instead of deleting them immediately.
- Whether to add a strict mode that rejects any `/OpenAction` regardless of subtype.

---

## A.5 Remaining Recommendations from v3.7

- Unify the two PDF parsing paths.
- Expand `.env.example` documentation.
- Validate PostgreSQL RLS with a live Postgres instance.
- Make alias-start matching configurable per merchant.
- Add future schema changes as new Alembic migrations rather than editing baseline.
## Section 31 — Cloud Code Audit & Dependency Audit (TASK-038.6 / 3.1, 3.5)

**Files added:** `docs/CLOUD_CODE_AUDIT.md`, `docs/DEPENDENCY_AUDIT.md`

**Files changed:** `backend/tests/test_local_first.py`

**Changes:**
- Scanned `backend/`, `frontend/src/`, and `scripts/` for imports or calls that could phone home.
- Confirmed `backend/local/settings.py` `FEATURE_FLAGS` already disable `plaid`, `stripe`, `smtp_email`, `oauth_login`, `telemetry`, `auto_update_check`, and `cloud_ml` by default.
- Confirmed the only backend network code is diagnostic (`backend/local/offline.py` network probe) or hardening (`backend/local/guards.py`).
- Confirmed frontend network calls are limited to `fetch` against the local FastAPI backend in `frontend/src/hooks/useAPI.ts`.
- Flagged `frontend/index.html` Google Fonts dependency as the only external asset; documented vendor option.
- Added `test_no_network_calls_in_offline_mode` asserting default offline gating raises on `guard_cloud_call("plaid")` and returns `False` for disabled features.
- Dependency audit concluded no production dependency phones home; `requests` is listed but not imported by application code.

**Why:** Requirements 3.1 and 3.5 require evidence that the local-first app does not initiate cloud/API calls by default. These documents provide that evidence and the gating policy for any future cloud features.

**Verification:**
```bash
python -m pytest backend/tests/test_local_first.py -q
```

---

## Section 32 — Offline Bootstrap Self-Test (TASK-038.7 / 3.2)

**Files added:** `backend/local/bootstrap.py`, `backend/tests/test_bootstrap.py`

**Files changed:** `backend/routers/health.py`, `backend/api.py`

**Changes:**
- Added `backend/local/bootstrap.py` with `run_bootstrap()`:
  - Checks importability of required Python modules (`fastapi`, `sqlalchemy`, `cryptography`, `pdfplumber`, `PIL`).
  - Checks optional OCR stack (`pdf2image`, `pytesseract`).
  - Checks external binaries `tesseract`, `pdftotext`, `pdftoppm` via `shutil.which` + `--version`.
  - Probes SQLite / configured database path with `PRAGMA integrity_check`.
  - Reports presence of local ML model artifacts.
  - Returns a serializable `BootstrapReport` with `ready` flag and per-check availability/required flags.
- Added public `GET /api/health/bootstrap` returning the bootstrap report.
- Extended `GET /api/health` to include `bootstrap_ready` and `bootstrap_checks`.
- Added `backend/tests/test_bootstrap.py` covering the report shape, serialization, `/api/health/bootstrap`, and health bootstrap fields.

**Why:** Requirement 3.2 needs a startup self-test that detects missing local dependencies and reports them without any network access. `run_bootstrap()` does exactly that and exposes it through existing health endpoints.

**Verification:**
```bash
python -m pytest backend/tests/test_bootstrap.py backend/tests/test_local_first.py -q
python -m pytest backend/tests -q
```
## Section 33 — Bulletproof SQLite (TASK-038.11 / Phase 3 Gap 3.4)

**Files added:** `backend/tests/test_recovery.py`

**Files changed:** `backend/database.py`, `backend/local/backup.py`, `backend/routers/upload.py`

**Changes:**
- SQLite reliability hardening in `backend/database.py`:
  - Added `_set_sqlite_pragmas` event listener enabling `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, and `PRAGMA foreign_keys=ON` for every SQLite connection.
  - Added `_sqlite_integrity_check` event listener that runs `PRAGMA integrity_check` on connect and raises `RuntimeError` on corruption.
  - Added `recover_sqlite_db(db_path, target_path)` helper that rebuilds a SQLite database via `iterdump()` and verifies the result with `PRAGMA integrity_check`. No network access.
- Automatic encrypted backups after every successful import:
  - Added `auto_backup_after_import()` and public aliases `backup_database()` / `restore_database()` in `backend/local/backup.py`.
  - Hooked the auto-backup call into the upload success path in `backend/routers/upload.py` for `sqlite:///` and `sqlcipher:///` databases.
  - Backup failures are swallowed so a transient backup issue cannot block the import.
- Added `backend/tests/test_recovery.py` with 6 tests:
  - `test_wal_mode_enabled`
  - `test_integrity_check_passes_on_fresh_db`
  - `test_integrity_check_fails_on_corrupt_db`
  - `test_recover_sqlite_db_rebuilds_valid_file`
  - `test_auto_backup_after_import`
  - `test_idempotent_reimport_after_simulated_crash`

**Why:** Requirement 3.4 requires WAL mode, automatic backups on every import, integrity checks, and crash recovery. These changes make the local SQLite path resilient against crashes and corruption while preserving the idempotent import contract from TASK-038.5.

**Verification:**
```bash
python -m pytest backend/tests/test_recovery.py -q
python -m pytest backend/tests -q
```


## Section 34 — Dependency Audit Finalization (TASK-038.8 / 3.1)

**Files changed:** `requirements.txt`

**Files added:** `docs/OFFLINE_BEHAVIOR.md`

**Tests added:** `backend/tests/test_local_first.py`

**Changes:**
- Removed `requests>=2.31.0` from `requirements.txt`; no backend runtime module imports `requests`, and the full test suite still passes.
- Added `test_no_forbidden_network_imports` to `backend/tests/test_local_first.py`, asserting that no runtime module under `backend/` or `phase3_pipeline/` imports `requests`, `urllib.request`, `http.client`, `httpx`, or `aiohttp`.
- Created `docs/OFFLINE_BEHAVIOR.md` documenting the Google Fonts external-asset decision and the vendor-font path for fully offline installers.
- Updated `shared/tasks/TASK-038-SUBTASKS.md` to mark TASK-038.8 complete.

**Why:** Requirement 3.1 requires a documented, tested guarantee that no runtime dependency initiates external network calls. Removing the unused `requests` entry and forbidding future HTTP-client imports codifies the local-first contract.

**Verification:**
```bash
python -m pytest backend/tests/test_local_first.py -q
python -m pytest backend/tests -q
```
Expected: `test_local_first.py` passes; full backend suite passes.

---

## Section 35 — Local Auth Keyfile Support (TASK-038.10 / 3.7)

**Files changed:** `backend/auth.py`, `backend/routers/auth.py`, `backend/schemas.py`, `backend/tests/test_hybrid_auth.py`

**Changes:**
- Wired the existing `LocalCryptoManager` and `LocalAuthManager` keyfile support into the API layer:
  - `POST /api/auth/boot` now accepts an optional `keyfile_path`; the path is validated (exists, ≥32 bytes), stored on the single local admin user, and used to derive the column-encryption key.
  - `POST /api/auth/login-json` accepts an optional `keyfile_path` and rejects the login if the account has a keyfile configured that is missing or mismatched.
  - `POST /api/auth/login` (OAuth2 form) stays password-only; if a keyfile is required it returns **401** with the message `Keyfile required; use /auth/login-json`.
  - Password change no longer requires the keyfile; the `change-password` endpoint verifies the current password directly and preserves the existing `keyfile_path` binding.
- Updated `backend/schemas.py::LocalBoot` to expose `keyfile_path`.
- Added four keyfile-specific tests in `backend/tests/test_hybrid_auth.py`:
  - `test_boot_with_keyfile_stores_path_and_allows_login`
  - `test_login_without_keyfile_after_keyfile_configured_fails`
  - `test_keyfile_mismatch_rejected`
  - `test_change_password_keeps_keyfile_binding`
- Updated `docs/TODO_FIRST.md` to mark item **3.7** as ✅ complete.

**Why:** Requirement 3.7 calls for a local auth system with an optional keyfile. The lower-level crypto and auth managers already implemented keyfile derivation, but the API layer ignored it. This section exposes and enforces keyfile binding through the public auth endpoints while keeping the password-only OAuth2 form path intact.

**Verification:**
```bash
python -m pytest backend/tests/test_hybrid_auth.py -q
python -m pytest backend/tests -q
```
Expected: full `test_hybrid_auth.py` suite passes; full backend suite passes.

---

## Section 36 — Local ML Retrain Pipeline (TASK-038.9 / 3.6)

**Files changed:**
- `backend/local/ml_pipeline.py`
- `backend/local/bootstrap.py`
- `backend/routers/ml.py`
- `backend/models.py`

**Files added:**
- `backend/tests/test_ml_pipeline.py`
- `alembic/versions/d9cf7c4a8fdf_add_trained_models_table.py`

**Changes:**
- Hardened `backend/local/ml_pipeline.py` with artifact integrity:
  - Added SHA-256 hashing of `local_model.pkl` and `local_vectorizer.pkl` after training.
  - Extended `model_meta.json` manifest with `model_sha256`, `vectorizer_sha256`, `trained_at`, and `version`.
  - Added `load_local_model_safe()` which refuses to load a model whose manifest is missing or whose hash mismatches, raising `TrainingError("Model integrity check failed")`.
  - `load_local_model()` now delegates to the safe loader so all existing call sites benefit.
- Updated `backend/local/bootstrap.py` `_model_artifacts_available()` to look for the actual pipeline outputs: `ml/local_model.pkl` + `ml/model_meta.json`.
- Added `TrainedModel` registry table to `backend/models.py` with user/tenant FKs, version, SHA-256, accuracy, support, and active flag.
- Extended `POST /api/ml/train` to:
  - Insert a registry row after successful training.
  - Mark prior rows for the user as inactive.
  - Return `model_sha256` and `version` in the response.
- Added `backend/tests/test_ml_pipeline.py` covering:
  - Manifest/hash creation.
  - Safe load with valid manifest.
  - Tampered-model rejection.
  - Missing-manifest rejection.
  - Endpoint authentication, insufficient labels, and successful training + registry persistence.
- Generated Alembic migration `d9cf7c4a8fdf_add_trained_models_table.py`.

**Why:** Requirement 3.6 requires a local-only retrain pipeline with no external ML APIs. Requirement 3.4d requires model-artifact integrity checks. This section completes the pipeline and protects against tampered or imported `joblib` artifacts.

**Verification:**
```bash
python -m pytest backend/tests/test_ml_pipeline.py -q
python -m pytest backend/tests/test_bootstrap.py -q
```
Expected: both focused suites pass with 0 failures.

---

---
