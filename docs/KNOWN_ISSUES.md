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

*Owner: James Clawd / Orchestrator*  
*Next review: After v3.10 Phase 1 completion*
