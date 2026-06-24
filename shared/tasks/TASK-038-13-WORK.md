# TASK-038.13 Hardened Test Suite — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Add property-based, corruption, recovery, and offline-mode tests to harden the local-first stack.

---

## Current state (pre-work done by orchestrator)

Read and analyzed existing test files:

- `backend/tests/test_local_first.py` — crypto, local auth, backup, offline self-test, SQLite pragmas, forbidden network imports.
- `backend/tests/test_bootstrap.py` — bootstrap report serialization, bootstrap endpoint.
- `backend/tests/test_recovery.py` — WAL mode, integrity check, corrupt DB, recovery, auto-backup after import, idempotent re-import after simulated crash.
- `backend/tests/test_hybrid_auth.py` — boot/login/refresh/change-password/brute-force tests.

**Gaps identified for TASK-038.13:**

1. No property-based tests for categorization, redaction, or transaction identity.
2. No dedicated test file for `test_crypto.py`.
3. No fuzz/corruption tests for PDF parser, upload validator, or column encryption.
4. No test that asserts the app binds to `127.0.0.1` by default.
5. No test that asserts `X-Tenant-ID` is ignored in SQLite mode.
6. No test that asserts local secret file has restrictive permissions.
7. No test that verifies `guard_cloud_call` blocks every `FEATURE_FLAGS` key.
8. No test that verifies `run_bootstrap()` performs no network calls.

---

## Jane's tasks

### 1. Create `backend/tests/test_crypto.py`

Move/extend crypto tests into a dedicated file for clarity. Coverage:

- `test_aes_gcm_authenticated`
  - Tampered ciphertext raises `AuthenticationError`/`EncryptionError`.
- `test_keyfile_factor_independence`
  - Keyfile-derived key cannot decrypt password-only ciphertext.
  - Password-only key cannot decrypt keyfile-bound ciphertext.
- `test_salt_uniqueness`
  - Two managers created with the same password have different salts.
- `test_argon2_parameters_resist_weak_input`
  - Very short password still produces a valid key; the manager does not crash.

Reuse helpers from `backend.local.crypto` and keep tests deterministic.

### 2. Add property-based categorization tests to `test_local_first.py`

Use `pytest` + simple property checks (no need for `hypothesis` unless already installed):

- `test_categorize_is_case_insensitive`
  - `"STARBUCKS"`, `"starbucks"`, `"StarBucks"` return the same category.
- `test_redact_description_masking`
  - A raw description with account number is masked in audit/export contexts but not stored.
- `test_generate_transaction_uid_is_deterministic`
  - Same inputs always produce the same `txn_uid`.
- `test_generate_transaction_uid_changes_when_amount_changes`
  - A different amount yields a different `txn_uid`.

### 3. Add parser corruption/fuzz tests to `backend/tests/test_parser_sandbox.py` (or new file)

- `test_guard_rejects_oversized_pdf`
  - Assert file over the configured max bytes is rejected.
- `test_guard_rejects_too_many_pages`
  - Assert a synthetic PDF (or a constructed object) exceeding the page limit is rejected.
- `test_guard_rejects_pdf_with_javascript`
  - Construct a minimal PDF containing `/JavaScript` and assert it is rejected.
- `test_parse_runs_in_subprocess`
  - Confirm that parsing is dispatched via subprocess; the parent process does not import heavy parser state before the guard passes.

### 4. Add single-user / offline security tests to `backend/tests/test_local_first.py`

- `test_default_bind_is_loopback`
  - Read `backend/api.py` or import `default_host` and assert it equals `"127.0.0.1"` when `TAXFLOW_BIND_LAN` is unset.
- `test_rls_middleware_ignored_on_sqlite`
  - Send a request with a nonsense `x-tenant-id` header to a SQLite-backed test app and confirm it succeeds (no RLS error).
- `test_all_feature_flags_default_to_false`
  - Iterate `FEATURE_FLAGS` and assert each value is `False`.
- `test_guard_cloud_call_blocks_each_feature`
  - For each key in `FEATURE_FLAGS`, call `guard_cloud_call(key)` and assert `RuntimeError`.
- `test_bootstrap_does_not_call_external_host`
  - Run `run_bootstrap()` and assert no external network host is resolved or contacted. This is mostly a code-review/static assertion, but add a regression test that the function completes without `socket.connect` to a non-loopback address.

### 5. Add local secret file permission test

- `test_local_secret_has_restrictive_permissions`
  - Boot once, check `LOCAL_SECRET_FILE` exists, and on Windows assert the file is not world-readable; on POSIX assert mode is `0o600`.
  - May require platform-specific helpers in `backend/local/keyring_secret.py`.

### 6. Add recovery stress tests

In `backend/tests/test_recovery.py`:

- `test_concurrent_read_during_backup`
  - Open a read transaction while `auto_backup_after_import` runs; ensure no corruption.
- `test_repeated_backup_manifest_increments`
  - Run `auto_backup_after_import` three times and confirm each backup file/manifest is distinct.

### 7. Update `docs/TODO_FIRST.md`

Mark Phase 3 Gap **3.10 Hardened test suite** as ✅ complete.

### 8. Update `CHANGES.md`

Add Section 37 (or next available) — Hardened Test Suite (TASK-038.13 / 3.10) documenting:
- Files added/changed: `backend/tests/test_crypto.py`, `test_local_first.py`, `test_parser_sandbox.py`/`test_pdf_fuzz.py`, `test_recovery.py`.
- New test categories: property-based, corruption, recovery, offline-mode, security.
- Verification commands and expected pass counts.

### 9. Run tests and report

```bash
python -m pytest backend/tests/test_crypto.py -q
python -m pytest backend/tests/test_local_first.py -q
python -m pytest backend/tests/test_parser_sandbox.py backend/tests/test_pdf_fuzz.py -q
python -m pytest backend/tests/test_recovery.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

Report pass/fail counts.

---

## Implementation notes

### Synthetic malicious PDF

Use `fpdf2` if available, or hand-craft a minimal bytes object:

```python
PDF_WITH_JS = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R /OpenAction 3 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [4 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Action /S /JavaScript /JS (app.alert(1)) >>
endobj
4 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000089 00000 n
0000000154 00000 n
0000000256 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
338
%%EOF
"""
```

Pass it through the existing `pdf_guard` functions, not the full parser, to keep tests fast and isolated.

### Parser subprocess assertion

```python
def test_pdf_parser_runs_in_subprocess():
    import multiprocessing
    from backend.parsers.sandbox_entry import parse_in_subprocess

    result = parse_in_subprocess(io.BytesIO(b"minimal pdf bytes"))
    # assert subprocess was used by checking process_id or returned metadata
```

### Property tests without Hypothesis

Keep them deterministic and simple. If `hypothesis` is already in dev requirements, you may use it, but avoid adding new production dependencies.

---

## Constraints

- Do not add new production dependencies.
- Do not change `FEATURE_FLAGS` defaults.
- Do not restart gateway or modify OpenClaw config.
- Keep all tests local-first / no network.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- New/updated test files covering crypto, property-based checks, parser fuzz, recovery stress, and offline/security assertions.
- Updated `docs/TODO_FIRST.md`.
- Updated `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
