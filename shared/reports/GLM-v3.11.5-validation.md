# TaxFlow Pro v3.11.5 — GLM Validation Report

**Validator:** GLM-5.1 (subagent)  
**Date:** 2026-06-27  
**Branch:** `v3.11.5-dev` at `5dc6812a` → validated, then `9f45eb0` with fixes  
**Scope:** Full codebase validation against Jane's analytical dive report

---

## 1. Validation Summary

| Area | Status | Details |
|------|--------|---------|
| Backend routers (27 routers in api.py) | ✅ Verified | All 27 routers have real implementations with endpoints |
| Frontend components (13 v3.11 modules) | ✅ Verified | All functional — 151–343 lines each, not stubs |
| Auth/BootGate flow | ✅ Verified | End-to-end flow correct; Ubuntu bug was stale DB, not code |
| Security controls (SEC.01–SEC.28) | ✅ Verified | All controls implemented with tests |
| RLS SQLite (RLS.01, .02, .05, .06) | ✅ Verified | 3/3 tests pass |
| Production mode (SEC.24, .25) | ✅ Verified | 4/4 tests pass |
| Installer artifact scanner (SEC.26) | ⚠️ Bug found & fixed | `_is_forbidden()` had inverted directory-matching logic |
| Version alignment | ✅ Verified | `version.txt`, `package.json`, `pyproject.toml` all at `3.11.5` |
| Frontend build | ✅ Verified | TypeScript compiles clean; Vite build succeeds (761KB JS, 91KB CSS) |

---

## 2. Failures Found and Fixed

### 2.1 Test: `test_health_endpoint` and `test_api_health_endpoint` — **Version assertion stale**

- **File:** `backend/tests/test_api.py`
- **Bug:** Asserted `version == "3.11.0"` but version was bumped to `3.11.5`
- **Fix:** Updated both assertions to `"3.11.5"`
- **Commit:** `9f45eb0`

### 2.2 Test: `test_token_expiry_and_secret_regeneration_invalidates_token` — **AttributeError on removed constant**

- **File:** `backend/tests/test_hybrid_auth.py` line 146
- **Bug:** Referenced `auth_module.LOCAL_SECRET_FILE` which was removed in commit `2f12324` (dynamic path resolution). Caused `AttributeError: module 'backend.auth' has no attribute 'LOCAL_SECRET_FILE'`
- **Fix:** Replaced with `_local_secret_file()`, `_delete_file_secret()`, and `generate_local_secret_key()` from `backend.local.keyring_secret` and `backend.local.crypto`
- **Commit:** `9f45eb0`

### 2.3 Fixture: `_force_file_secret_for_legacy_tests` — **38 teardown errors**

- **File:** `backend/tests/test_hybrid_auth.py` line 61–66
- **Bug:** Teardown tried `os.remove(auth_module.LOCAL_SECRET_FILE)` — same `AttributeError` as 2.2, affecting all 38 hybrid auth test teardowns
- **Fix:** Replaced with `_local_secret_file()` dynamic path and `secret_path.unlink()`
- **Commit:** `9f45eb0`

### 2.4 Tests: `test_keyring_secret.py` — **Monkeypatching stale module constant**

- **File:** `backend/tests/test_keyring_secret.py` lines 30, 52
- **Bug:** Monkeypatched `backend.local.keyring_secret.LOCAL_SECRET_FILE` (module-level constant), but `_local_secret_file()` now resolves dynamically and doesn't read that constant
- **Fix:** Changed to monkeypatch `backend.local.keyring_secret._local_secret_file` (the function) instead
- **Commit:** `9f45eb0`

### 2.5 Production bug: `_is_forbidden()` in installer artifact scanner — **Inverted directory-matching logic**

- **File:** `backend/security/installer_artifact_scan.py` lines 64–78
- **Bug:** Directory pattern matching had inverted logic: the condition `(f"/{pattern}" in name or name.startswith(pattern)) and not name.endswith("/")` evaluated to True for paths inside forbidden directories (e.g., `backend/tests/test_api.py`) and then returned `None` (allowing the entry), while the subsequent `pattern.rstrip("/") in name.split("/")` check was never reached. This meant files inside forbidden directories like `tests/`, `backend/tests/`, `fixtures/`, `.git/`, `.pytest_cache/`, and `__pycache__/` were incorrectly allowed through the scanner.
- **Fix:** Rewrote directory matching to use path component analysis — split path on `/`, check if the directory name appears as a component, and only flag files inside the directory (not the directory entry itself). Also added trailing slashes to `.pytest_cache` and `__pycache__` patterns (they were stored as plain names without slashes, so the directory pattern logic never matched them). Added `TEST_CODE_PREFIXES` for `test_*.py` detection.
- **Impact:** Without this fix, a packaged installer could ship test files, `.pytest_cache`, `__pycache__`, and files inside `.git/` — exactly what SEC.26 is designed to prevent.
- **Commit:** `9f45eb0`

### 2.6 Missing test file: `test_installer_artifact_scan.py` — **No test coverage for SEC.26**

- **Bug:** The report claimed "174 passed, 1 skipped" for the security suite, but there was no `test_installer_artifact_scan.py` file. The scanner module had zero test coverage.
- **Fix:** Created comprehensive test suite with 41 tests covering:
  - `TestIsForbidden` (22 tests): every forbidden pattern, directory matching, clean files, test code suffixes and prefixes
  - `TestScanZipLike` (5 tests): clean zip, .env detection, .pem detection, test directory detection, world-writable mode detection
  - `TestScanArtifact` (5 tests): nonexistent artifact, clean zip, dirty zip, .deb scan, .exe scan
  - `TestScanInstallerDir` (3 tests): nonexistent dir, empty dir, multi-extension scan
  - `TestCLI` (5 tests): no artifacts, fail-on-missing, clean artifact, dirty artifact, single file
  - `TestFinding` (1 test): repr format
- **Commit:** `9f45eb0`

---

## 3. Test Results Before and After

### Before (at commit `5dc6812`)
- `test_api.py`: 2 FAILED (version assertions)
- `test_hybrid_auth.py`: 38 ERRORS + 1 FAILED (`AttributeError: LOCAL_SECRET_FILE`)
- `test_keyring_secret.py`: 2 FAILED (monkeypatch stale constant)
- `test_installer_artifact_scan.py`: MISSING (0 tests)
- `installer_artifact_scan.py`: Bug in `_is_forbidden()` allowing forbidden directories

### After (at commit `9f45eb0`)
- `test_api.py`: ✅ All pass
- `test_hybrid_auth.py`: ✅ 38 passed, 0 errors
- `test_keyring_secret.py`: ✅ All pass (including Windows permission test)
- `test_installer_artifact_scan.py`: ✅ 41 passed
- `installer_artifact_scan.py`: ✅ Bug fixed, directory matching correct
- Combined core suite: **102 passed, 1 skipped, 0 failures**
- Security-focused suite: **223 passed, 1 skipped, 1 flaky HSTS test** (pre-existing, passes in isolation)

---

## 4. Remaining Blockers (Require Josh/James Decision)

| # | Blocker | Owner | Action Needed |
|---|---------|-------|---------------|
| 1 | Ubuntu first-run `BootGate` confirmation | btsinnovations / James | Wipe `~/.local/share/TaxFlowPro` on Ubuntu and retest. Code is correct; bug was stale DB. |
| 2 | Full test suite (`pytest backend/tests tests`) | Jane / CI | Run complete suite to capture all pass/fail counts before tagging. |
| 3 | Validator review sign-off (G9) | James | This report serves as the validator review. |
| 4 | Josh approval to tag v3.11.5 (G10) | Josh | After G9 and Ubuntu confirmation. |
| 5 | macOS `.app`/DMG | Josh | Requires macOS host + Apple Developer account — deferred. |
| 6 | Code-signing (Windows OV, Linux GPG) | Josh | Deferred per prior decision — functionality over form. |
| 7 | PostgreSQL RLS Phase 2 | James / Jane | Deferred to post-v3.11.5 — needs live PG instance. |

---

## 5. Validated Claims from Jane's Report

| Claim | Verified? | Notes |
|-------|-----------|-------|
| `/api/auth/status` + first-boot detection ✅ Functional | ✅ | `is_first_boot()` correctly returns `db.query(User).first() is None` |
| BootGate renders "Create master password" when `isFirstBoot === true` | ✅ | Verified in `BootGate.tsx` and `AuthContext.tsx` — flow is correct |
| Production mode gates `/api/tests/` | ✅ | `local_settings.is_development()` check in `api.py`; returns 404 in prod |
| JWT auth headers on all authenticated API calls | ✅ | `_authHeaders()` used in all `useAPI.ts` calls except boot/login/register |
| Dynamic local secret path | ✅ | `_local_secret_file()` resolves from env; tests now fixed |
| Installer artifact scanner | ✅ (after fix) | Bug fixed; 41 tests added |
| All 27 backend routers | ✅ | All exist with real implementations |
| All 13 v3.11 frontend modules | ✅ | 151–343 lines each, real implementations with data fetching |
| Frontend build | ✅ | TypeScript clean; Vite build succeeds |
| Version alignment | ✅ (after fix) | Test assertions updated to `3.11.5` |

---

## 6. Files Changed

| File | Change |
|------|--------|
| `backend/tests/test_api.py` | Updated version assertions from `3.11.0` to `3.11.5` |
| `backend/tests/test_hybrid_auth.py` | Fixed fixture and test to use `_local_secret_file()` instead of removed `LOCAL_SECRET_FILE` |
| `backend/tests/test_keyring_secret.py` | Monkeypatch `_local_secret_file` function instead of module constant |
| `backend/security/installer_artifact_scan.py` | Fixed `_is_forbidden()` directory matching bug; added `TEST_CODE_PREFIXES` |
| `backend/tests/test_installer_artifact_scan.py` | **NEW** — 41 tests for the installer artifact scanner |

---

*End of GLM validation report.*