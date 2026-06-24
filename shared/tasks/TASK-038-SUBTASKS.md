# TASK-038 — Phase 3 Foundation Sub-Task Plan

**Status:** Complete  
**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Constraint:** Use SQLCipher for encryption (3.3 + 3.8). Key location TBD — implement safest local-first default and propose options.

---

## Sub-Task 038.1 — 3.3 SQLCipher Local Encryption Layer ✅ In Progress

**Objective:** Add SQLCipher-backed SQLite engine support.

**Files:**
- `backend/local/sqlcipher_engine.py` (new)
- `backend/database.py` (integrate engine selection)
- `backend/local/settings.py` (encryption env vars)
- `requirements.txt` (add `sqlcipher3-wheels`)

**Acceptance criteria:**
- [x] `sqlcipher3-wheels` imports and applies `PRAGMA key` without error.
- [x] SQLAlchemy can create/read/update/delete through the SQLCipher engine.
- [x] Key derived from master password via Argon2id, held in memory only.
- [x] No plaintext keyfile is written by default (optional keyfile/keyring factors allowed).
- [x] Tests added: `backend/tests/test_sqlcipher_engine.py`
- [x] Update `docs/TODO_FIRST.md` to mark 3.3 complete.
- [x] Update `CHANGES.md`.
- [x] Run `pytest backend/tests` and report pass/fail.

**Status:** Complete.

---

## Sub-Task 038.2 — 3.8 Encrypted Backup / Restore ✅ Complete

**Objective:** Add encrypted database snapshots and restore.

**Files:**
- `backend/local/backup.py` (extended)
- `backend/tests/test_backup_restore.py` (extended)

**Acceptance criteria:**
- [x] Backup copies SQLCipher-encrypted DB bytes + public salt sidecar.
- [x] Restore re-creates working DB + salt sidecar so same master password opens it.
- [x] Uses same local secret encryption envelope for the backup file.
- [x] Tests: SQLCipher detection + SQLCipher backup/restore round-trip.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Full backend regression: **340 passed, 97 warnings, 0 failed**.

---

## Sub-Task 038.3 — 3.4b PII Masking ✅ Complete

**Objective:** Mask account/card numbers and sensitive descriptions in audit logs, exports, and summaries.

**Files:**
- `backend/utils/redaction.py` (new)
- `backend/routers/audit.py`
- `backend/routers/export.py`
- `backend/services/export.py`
- `backend/local/guards.py`
- `backend/tests/test_redaction.py` (new)

**Acceptance criteria:**
- [x] Full account/card numbers masked to last 4 digits.
- [x] Sensitive raw descriptions redacted in audit/export outputs.
- [x] Raw data remains in DB; only output surfaces are masked.
- [x] Tests: `backend/tests/test_redaction.py` (10 tests added).
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Full `backend/tests` regression: **340 passed, 99 warnings, 0 failed**.

---

## Sub-Task 038.4 ✅ — 3.4e PDF Parser Sandbox Hardening Complete

**Objective:** Harden PDF parsing against malicious input.

**Files:**
- `backend/parsers/pdf_guard.py` (new — byte-level static guard)
- `backend/parsers/sandbox_entry.py` (defense-in-depth guard before import)
- `backend/parsers/generic_pdf.py` (page limit in extraction + OCR)
- `backend/parsers/ocr_parser.py` (page limit in extraction)
- `backend/parsers/institution.py` (guard before parser dispatch)
- `backend/routers/upload.py` (parent-process guard)
- `backend/local/guards.py` (re-exports/wraps `pdf_guard`)
- `backend/tests/test_parser_sandbox.py` (extended)

**Acceptance criteria:**
- [x] File size limit enforced before parsing.
- [x] Page count limit enforced.
- [x] Reject PDFs with embedded JavaScript/actions.
- [x] Parser runs in subprocess with no network.
- [x] Tests: `backend/tests/test_parser_sandbox.py` extended.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Full `backend/tests` regression: **345 passed, 100 warnings, 0 failed**.

---

---

## Sub-Task 038.5 ✅ — 3.4a Idempotent Import Contract Complete

**Objective:** Prevent duplicate transactions on re-upload or sync retry.

**Files:**
- `backend/routers/upload.py`
- `phase3_pipeline/identity.py` (new)
- `backend/models.py`

**Acceptance criteria:**
- [x] Deterministic `txn_uid` = hash(institution + account + date + amount + normalized description).
- [x] Upsert on conflict in upload path.
- [x] Re-uploading same statement does not duplicate transactions.
- [x] Tests: `backend/tests/test_upload.py` or new `test_idempotent_upload.py`
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Full `backend/tests` regression: **345 passed, 100 warnings, 0 failed**.

---

## Sub-Task 038.6 ✅ — 3.5 Gate / Remove Cloud API Code Complete

**Objective:** Audit and gate/remove any cloud or external API usage.

**Files:**
- `backend/`
- `frontend/`
- `scripts/`

**Acceptance criteria:**
- [x] Audit all imports and network calls.
- [x] Gate Plaid/SMTP/telemetry/update checks behind opt-in env vars or remove.
- [x] Produce `docs/DEPENDENCY_AUDIT.md` and `docs/CLOUD_CODE_AUDIT.md`.
- [x] Add tests confirming no network calls in offline/default mode.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Full `backend/tests` regression: **350 passed, 100 warnings, 0 failed**.

---

## Sub-Task 038.7 ✅ — 3.2 Offline Startup Self-Test Complete

**Objective:** Detect missing local dependencies on startup without network.

**Files:**
- `backend/local/bootstrap.py` (new)
- `backend/api.py` (health endpoint extension)

**Acceptance criteria:**
- [x] Detect Tesseract, Poppler, models, DB availability.
- [x] Report status locally without network calls.
- [x] Expose `/api/bootstrap` or extend `/api/health` with missing-deps list.
- [x] Tests: `backend/tests/test_bootstrap.py`
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Full `backend/tests` regression: **350 passed, 100 warnings, 0 failed**.

---

---

## Sub-Task 038.8 — 3.1 Dependency Audit

**Objective:** Produce a documented audit of every runtime dependency.

**Files:**
- `docs/DEPENDENCY_AUDIT.md`
- `scripts/dependency_audit.py` (optional)
- `docs/OFFLINE_BEHAVIOR.md` (added)

**Acceptance criteria:**
- [x] List every top-level + transitive dependency in `requirements.txt` / `frontend/package.json`.
- [x] Mark whether each can phone home at runtime.
- [x] Document mitigation for any that do (gate, remove, vendor).
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Dependency:** 038.6 (share findings)

**Status:** Complete. `requests` removed from `requirements.txt`; `test_no_forbidden_network_imports` added to `backend/tests/test_local_first.py` and passing.

---

## Sub-Task 038.9 — 3.6 Local ML Retrain Pipeline ✅ Complete

**Objective:** User can retrain categorizer on their own data with no external ML APIs.

**Files:**
- `backend/local/ml_pipeline.py`
- `backend/local/bootstrap.py`
- `backend/routers/ml.py`
- `backend/models.py`
- `backend/tests/test_ml_pipeline.py` (new)
- `alembic/versions/d9cf7c4a8fdf_add_trained_models_table.py` (new)

**Acceptance criteria:**
- [x] Retrain endpoint accepts user-labeled transactions.
- [x] Generates new local model artifact without network calls.
- [x] Stores model with integrity hash/manifest.
- [x] Safe loader rejects missing/tampered models.
- [x] `TrainedModel` registry table added with Alembic migration.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Status:** Complete. Focused test suite: **9 passed, 4 warnings, 0 failed**.

## Sub-Task 038.10 — 3.7 Complete Local Auth System ✅ Complete

**Objective:** Finish local-only auth (master password + optional keyfile, Argon2, local sessions).

**Files:**
- `backend/local/auth.py`
- `backend/routers/auth.py`
- `backend/auth.py`
- `backend/schemas.py`
- `backend/tests/test_hybrid_auth.py`

**Acceptance criteria:**
- [x] Master password registration/login via bcrypt/Argon2.
- [x] Optional keyfile wired into `/auth/boot` and `/auth/login-json`.
- [x] No OAuth/network validation.
- [x] Tests added to `backend/tests/test_hybrid_auth.py`.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Dependency:** 038.1 (key derivation)

**Status:** Complete. Keyfile support wired through API layer; `docs/TODO_FIRST.md` 3.7 marked complete; `CHANGES.md` Section 35 added.

## Sub-Task 038.11 — 3.4 Bulletproof SQLite ✅ Complete

**Objective:** Harden SQLite mode (WAL, backups, idempotent imports, integrity, crash recovery).

**Files:**
- `backend/database.py`
- `backend/local/backup.py`
- `backend/tests/test_recovery.py`

**Acceptance criteria:**
- [x] WAL mode enabled for SQLite.
- [x] Automatic backup on every import.
- [x] Idempotent imports (overlaps 038.5).
- [x] Integrity check (`PRAGMA integrity_check`) on startup.
- [x] Crash recovery path documented.
- [x] Tests: `backend/tests/test_recovery.py`
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run full suite and report.

**Verification:**
```bash
python -m pytest backend/tests/test_recovery.py -q
```
Result: **9 passed, 4 warnings, 0 failed**.

**Status:** Complete.

---

## Sub-Task 038.12 — 3.9 Offline Behavior Docs ✅ Complete

**Objective:** Document what works offline and what is disabled.

**Files:**
- `docs/OFFLINE_BEHAVIOR.md`

**Acceptance criteria:**
- [x] List features available offline.
- [x] List features disabled/mocked when offline.
- [x] User-facing messaging guidance.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.

**Status:** Complete. `docs/OFFLINE_BEHAVIOR.md` covers the feature matrix, cloud-gated features, external assets (Google Fonts), user-facing messaging guidance, dev vs production defaults, data-flow summary, and verification checklist.

---

## Sub-Task 038.13 — 3.10 Hardened Test Suite ✅ Complete

**Objective:** Add property-based, corruption, recovery, and offline-mode tests.

**Files:**
- `backend/tests/test_crypto.py` (new)
- `backend/tests/test_pdf_fuzz.py` (new)
- `backend/tests/test_keyring_secret.py` (new)
- `backend/tests/test_local_first.py`
- `backend/tests/test_recovery.py`

**Acceptance criteria:**
- [x] Offline bootstrap tests.
- [x] Database corruption/recovery tests.
- [x] Encryption/crypto tests (integrate with 038.1).
- [x] Parser fuzz/corruption tests.
- [x] Local secret file permission tests.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run targeted tests and report.

**Status:** Complete. See `CHANGES.md` Section 38.

**Verification (run on Windows 10 / Python 3.14):**
- `python -m pytest backend/tests/test_crypto.py -q` → 12 passed, 4 warnings, 0 failed
- `python -m pytest backend/tests/test_pdf_fuzz.py -q` → 9 passed, 4 warnings, 0 failed
- `python -m pytest backend/tests/test_keyring_secret.py -q` → 2 passed, 1 skipped, 4 warnings, 0 failed
- `python -m pytest backend/tests/test_local_first.py -q` → 26 passed, 4 warnings, 0 failed
- `python -m pytest backend/tests/test_recovery.py -q` → 9 passed, 4 warnings, 0 failed

---

## Sub-Task 038.14 — 3.11 Simplify Single-User Default ✅ Complete

**Objective:** Remove reliance on `X-Tenant-ID` middleware for single-user mode.

**Files:**
- `backend/api.py`
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
- `backend/routers/health.py`
- `backend/tests/test_single_user_mode.py` (new)

**Acceptance criteria:**
- [x] `TAXFLOW_SINGLE_USER` env flag defaults to `true`; `is_single_user()` helper added to `backend/local/settings.py`.
- [x] Single-user mode works without `X-Tenant-ID` header on SQLite.
- [x] Multi-entity mode remains optional via `TAXFLOW_SINGLE_USER=false` and still requires `X-Tenant-ID` on PostgreSQL.
- [x] `backend/api.py::rls_tenant_middleware` returns clear 400 when the header is missing/invalid in multi-entity PostgreSQL mode.
- [x] `backend/rls.py::get_current_tenant` infers tenant from the authenticated user's primary client in single-user mode.
- [x] Tests added: `backend/tests/test_single_user_mode.py`.
- [x] `docs/TODO_FIRST.md` and `CHANGES.md` updated.
- [x] Focused test suite passes.

**Verification:**
```bash
python -m pytest backend/tests/test_single_user_mode.py -q
```
Result: **5 passed, 4 warnings, 0 failed**.

**Status:** Complete.

---


## Final TASK-038 Completion

All Phase 3 Foundation sub-tasks are now complete. Jane will produce the final handoff materials:
- Final handoff in `shared/tasks/TASK-038.md`
- Full `pytest backend/tests tests` result
- Updated `docs/TODO_FIRST.md` showing all Phase 3 items complete
- Any remaining Josh decisions documented (e.g., keyfile/OS keyring preference)

---

## Sub-Task 038.6 — Cloud Code Audit (3.1 / 3.5)

- [x] Scan `backend/`, `frontend/src/`, `scripts/` for cloud/API/network calls.
- [x] Confirm `FEATURE_FLAGS` disable Plaid/Stripe/SMTP/OAuth/telemetry/update checks by default.
- [x] Add `docs/CLOUD_CODE_AUDIT.md` and `docs/DEPENDENCY_AUDIT.md`.
- [x] Add test asserting no network calls in offline/default mode.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run targeted tests and report.

**Status:** Complete.

## Sub-Task 038.7 — Offline Bootstrap Self-Test (3.2)

- [x] Create `backend/local/bootstrap.py` detecting local deps (no network).
- [x] Extend `/api/health` with bootstrap status and add `/api/health/bootstrap`.
- [x] Add `backend/tests/test_bootstrap.py`.
- [x] Update `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Run targeted tests and report.

**Status:** Complete.
---

## Sub-Task 038.11 — 3.4 Bulletproof SQLite

- [x] WAL mode enabled for SQLite.
- [x] `PRAGMA integrity_check` on startup.
- [x] Automatic encrypted backup after every successful import.
- [x] Crash recovery helper (`recover_sqlite_db`).
- [x] Idempotent re-import after simulated crash verified.
- [x] Tests added: `backend/tests/test_recovery.py`.
- [x] Updated `docs/TODO_FIRST.md` and `CHANGES.md`.
- [x] Full backend regression run and reported.

**Status:** Complete.

