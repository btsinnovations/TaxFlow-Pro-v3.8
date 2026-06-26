# TaxFlow Pro v3.9.2 — Known Issues

**Date:** 2026-06-24  
**Status:** v3.9.2 tagged with these items tracked for v3.10

## 1. Full Regression Suite Isolation Failure

**Problem:** Running the complete test suite with `pytest backend/tests tests` fails with cascading errors (version mismatch, 401s on CRUD tests, missing tables, duplicate-table teardown errors).

**Root cause:** `backend/tests/conftest.py` uses a shared on-disk SQLite database (`sqlite:///./test_taxflow.db`) and a single global engine. Multiple fixtures and tests call `Base.metadata.create_all()` / `drop_all()` on the same engine, and `auth_client` mutates the shared `client.headers`. State leaks between tests.

**Evidence (observed during attempted full run 2026-06-24):**
- `test_health_endpoint` sees `version == 3.9.1` after earlier tests corrupt state.
- `test_client_crud` returns 401 due to residual auth fixture state.
- Teardown errors include `no such table: categorization_rules`, `table refresh_tokens already exists`.

**Fix scheduled for:** v3.10 Phase 1 (test-harness refactor).

**Planned remediation:**
- Replace shared `test_taxflow.db` with a fresh per-test database (temporary file or in-memory SQLite).
- Use Alembic migrations (`upgrade head`) instead of `Base.metadata.create_all()` so migration-only columns/triggers exist.
- Stop mutating `client.headers` in `auth_client`; yield an authorized client copy instead.
- Audit `test_audit_trail.py` and any other tests that maintain their own `db` fixtures on the global engine.

**Acceptance criterion:** `pytest backend/tests tests -q` passes with 0 failures.

## 2. CHANGES.md Section Numbering Drift

**Problem:** Section 36 in `CHANGES.md` is labeled “Local ML Retrain Pipeline,” which does not match the release checklist’s expected “Secrets File Support + URL Redaction.” There are also duplicate Section 38 entries.

**Impact:** Low. The actual work is documented; only the section titles/numbers are inconsistent.

**Fix scheduled for:** Next documentation cleanup pass, ideally as part of v3.10 release notes.

## 3. Full Regression Not Required for v3.9.2 Tag

**Decision:** v3.9.2 ships based on focused security-sprint suites passing. The full regression green-light is a gate for v3.10, not v3.9.2.

**Focused suites verified:**
- `backend/tests/test_backup_restore.py` + `test_recovery.py` + `test_audit_trail.py` — 24 passed, 0 failed.
- Individual TASK-036 through TASK-039 targeted suites pass.

---

## 4. Missing API Endpoints for v3.10 Desktop Smoke Test

**Date:** 2026-06-24  
**Status:** Known issue; deferred to v3.11

**Problem:** The v3.10 packaged desktop smoke test revealed two missing backend endpoints required for a complete end-to-end workflow:

- `POST /api/transactions/` — manual transaction creation (server-side)
- `POST /api/backup/now` — on-demand backup trigger (server-side)

**Evidence:**
- Windows smoke test v4: both endpoints returned `HTTP 404 Not Found`.
- Export CSV (`/api/export/transactions`) and auth boot work fine.

**Why deferred:**
- v3.10 scope is locked to packaging-only.
- These endpoints are part of the full bookkeeping feature set already planned for v3.11.
- Adding them now would require product-code changes outside v3.10 scope.

**Fix scheduled for:** v3.11 (Bookkeeping Platform Expansion). Likely owned by modules:
- 3.11.03 Unified Register + Transactions (`backend/routers/transactions.py`)
- 3.11.11 Reports Center or a dedicated `backup.router` endpoint

**Workaround in v3.10:**
- Users can still import transactions via `/api/upload` when available.
- Backups are created automatically after import via `backend/local/backup.py`.

---

## 5. Frontend Auth Token Handling in Packaged Builds

**Date:** 2026-06-25  
**Status:** Known issue; fix pushed to v3.10-dev, pending verification in fresh `.deb` install

**Problem:** The packaged desktop app (Linux `.deb`) serves the UI from the same origin as the API, but dashboard/audit/account/client endpoints return 401 because the frontend does not reliably attach the Bearer token to all API calls.

**Evidence:**
- Ubuntu `.deb` install 2026-06-25: `GET /api/dashboard/stats`, `/api/clients/`, `/api/accounts/`, `/api/audit/`, `/api/tax/` all return 401 after auth boot.
- The `AuthContext` stores the token in `localStorage`, but many `useAPI.ts` helpers were not sending it.

**Fix applied to v3.10-dev:**
- `frontend/src/hooks/useAPI.ts` now sends `Authorization: Bearer <token>` on all protected calls.
- `getTests()` / `runTests()` are no-ops in production builds.

**Verification needed:**
- Fresh `.deb` build + install on Ubuntu must show no 401s in browser console.

**If verification fails:** escalate to v3.11 for a proper `fetchWithAuth` refactor and request interceptor.

---

## 6. Extension Noise in Browser Console

**Date:** 2026-06-25  
**Status:** Not a TaxFlow bug

**Problem:** Browser console shows `MaxListenersExceededWarning` and `ObjectMultiplex` warnings from `contentscript.js`.

**Root cause:** Browser extension (likely MetaMask or another wallet/injecting extension) injecting content scripts into the local app.

**Action:** None required for TaxFlow.

---

## 6. v3.11.5 Scaffold Known Issues

**Date:** 2026-06-26
**Status:** Scaffold in progress on `v3.11.5-dev`

### 6.1 macOS `.app` + DMG Packaging
- **Issue:** macOS bundle is scaffolded but cannot be built or signed on the current Windows/Linux hosts.
- **Impact:** macOS packaging remains deferred until a macOS host is available.
- **Workaround:** Documented in `shared/specs/v3.11.5-security-packaging-spec.md` as a staged deferral.

### 6.2 RLS Validation Requires Live PostgreSQL
- **Issue:** PostgreSQL Row-Level Security policies are scaffolded but the full isolation test suite needs a live PostgreSQL instance.
- **Impact:** `backend/tests/test_rls_postgres.py` is stubbed and skipped on SQLite.
- **Workaround:** SQLite builds rely on application-level tenant filtering; PostgreSQL policies are applied via Alembic migration.

### 6.3 Public Code-Signing / Notarization Deferred
- **Issue:** Windows OV certs, Apple Developer membership, and GPG signing keys have not been purchased/generated.
- **Impact:** Installers will be unsigned for friends/family distribution.
- **Workaround:** Trust-signal options documented; signing will be wired into build scripts only after explicit Josh approval.

### 6.4 Production Mode is a Skeleton
- **Issue:** `TAXFLOW_ENV=production` removes `/api/tests/` and reports production mode via health endpoints, but additional debug-only middleware/routes may need to be gated as they are identified.
- **Impact:** No functional bug, but the production-mode surface will be tightened during implementation.

---

*Owner: James Clawd / Orchestrator*  
*Next review: After v3.11.5 scaffold commit or full implementation kickoff*
