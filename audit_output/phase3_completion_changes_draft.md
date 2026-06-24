# CHANGES.md Draft Sections for Remaining Phase 3 Foundation Tasks

These sections should be inserted into `CHANGES.md` after TASK-038.13 and 038.14 pass their tests.

---

## Section 38 — Hardened Test Suite (TASK-038.13 / 3.10)

**Files changed:**
- `backend/tests/test_local_first.py`
- `backend/tests/test_recovery.py`

**Files added:**
- `backend/tests/test_crypto.py` (or equivalent crypto-focused tests)
- `backend/tests/test_parser_sandbox.py` / `backend/tests/test_pdf_fuzz.py`

**Changes:**
- Added property-based tests for transaction categorization, redaction masking, and deterministic transaction UID generation.
- Added dedicated `backend/tests/test_crypto.py` covering AES-GCM authentication failure, keyfile-factor independence, salt uniqueness, and Argon2 weak-input handling.
- Added parser corruption/fuzz tests: oversized PDF rejection, too-many-pages rejection, PDF-with-JavaScript rejection, and subprocess-based parser isolation.
- Added offline/security assertions: default bind to `127.0.0.1`, `X-Tenant-ID` ignored on SQLite, all `FEATURE_FLAGS` default to `False`, `guard_cloud_call` blocks each feature, bootstrap performs no external network calls, and local secret file has restrictive permissions.
- Added recovery stress tests: concurrent read during backup and repeated backup manifest increments.

**Verification:**
```bash
python -m pytest backend/tests/test_crypto.py -v
python -m pytest backend/tests/test_local_first.py -v
python -m pytest backend/tests/test_parser_sandbox.py backend/tests/test_pdf_fuzz.py -v
python -m pytest backend/tests/test_recovery.py -v
```
Expected: all focused suites pass with 0 failures.

---

## Section 39 — Simplify Single-User Default (TASK-038.14 / 3.11)

**Files changed:**
- `backend/local/settings.py`
- `backend/rls.py`
- `backend/routers/accounts.py`
- `backend/routers/clients.py`
- `backend/routers/depreciation.py`
- `backend/routers/flags.py`
- `backend/routers/gl.py`
- `backend/routers/rules.py`
- `backend/routers/tax.py`
- `backend/routers/transactions.py`
- `backend/routers/upload.py`

**Files added:**
- `backend/tests/test_single_user_mode.py`
- Updated `.env.example`

**Changes:**
- Added `TAXFLOW_SINGLE_USER` env flag defaulting to `true` and `is_single_user()` helper in `backend/local/settings.py`.
- Updated `backend/rls.py::get_current_tenant` to infer the tenant from the authenticated user's primary client in single-user mode, bypassing the `X-Tenant-ID` header requirement.
- Updated remaining strict `X-Tenant-ID` header checks in routers to only raise 400 in multi-entity PostgreSQL mode (`TAXFLOW_SINGLE_USER=false`).
- Added `backend/tests/test_single_user_mode.py` verifying default single-user mode, header-less SQLite requests, ignored arbitrary `X-Tenant-ID` header, and multi-entity header requirement under monkeypatched PostgreSQL mode.
- Updated `.env.example` with `TAXFLOW_SINGLE_USER=true` documentation.

**Migration note:** Existing multi-entity PostgreSQL installs must set `TAXFLOW_SINGLE_USER=false` after upgrading to retain header-based tenant routing.

**Verification:**
```bash
python -m pytest backend/tests/test_single_user_mode.py -v
python -m pytest backend/tests/test_hybrid_auth.py -v
python -m pytest backend/tests/test_local_first.py -v
```
Expected: all focused suites pass with 0 failures.

---

*Draft ready for copy-paste into CHANGES.md once TASK-038.13 and 038.14 test suites are green.*
