# CHANGES.md Draft Sections for Security Sprint

These sections should be inserted into `CHANGES.md` after TASK-036, 037, 038-Entropy, and 039 pass their tests.

---

## 36. Sensitive Data in Process Arguments (TASK-036)

**Files changed:** `backend/local/settings.py`, `backend/database.py`, `.env.example`

**Files added:** `backend/local/secrets_loader.py`, `backend/tests/test_secret_handling.py`

**Changes:**
- Added `TAXFLOW_SECRETS_FILE` support. A key=value file outside version control can now supply `DATABASE_URL`, `TAXFLOW_DB_PASSWORD`, `TAXFLOW_DB_KEYFILE`, and `TAXFLOW_DB_KEYRING_TOKEN`.
- Secrets file values take precedence over environment variables, keeping credentials out of `/proc/<pid>/environ` on shared systems.
- Added `redact_url()` helper to strip passwords from URLs before logging.
- Updated `.env.example` with guidance on secrets-file vs. environment-variable storage.

**Verification:**
```bash
python -m pytest backend/tests/test_secret_handling.py -v
```
Expected: **3 passed, 0 failed**.

---

## 37. Dependency Confusion Mitigation (TASK-037)

**Files changed:** `README.md` or `BUILDER_MANUAL.md`

**Files added:** `pyproject.toml`, `requirements-lock.txt`, `backend/tests/test_dependency_confusion.py`

**Changes:**
- Added `pyproject.toml` with non-publishable project name `taxflow-pro-private` to avoid accidental or malicious PyPI squatting.
- Generated `requirements-lock.txt` with exact pinned versions and SHA-256 hashes.
- Documented internal package namespace policy: future Python internal packages must use `taxflow_private_*` or remain under `backend/`; npm packages must use the `@taxflow/` private scope.
- Added test asserting lockfile presence and pinned coverage of top-level requirements.

**Verification:**
```bash
python -m pytest backend/tests/test_dependency_confusion.py -v
```
Expected: **2 passed, 0 failed**.

---

## 38. Weak Entropy Audit (TASK-038-Entropy-Audit)

**Files changed:** None required; existing security modules already use `secrets`.

**Files added:** `backend/local/security_random.py`, `backend/tests/test_entropy_audit.py`

**Changes:**
- Audited `backend/`, `phase3_pipeline/`, and `scripts/` for `import random`, `uuid.uuid1()`, and `numpy.random` usage.
- No security-critical usage of the stdlib `random` module was found.
- Added centralized `backend/local/security_random.py` helpers: `secure_token`, `secure_urlsafe_token`, `secure_random_int`, `secure_alphanumeric`.
- Added regression test that security-critical modules (`backend/auth.py`, `backend/local/crypto.py`, `backend/local/keyring_secret.py`, `backend/routers/auth.py`) do not import `random`.

**Verification:**
```bash
python -m pytest backend/tests/test_entropy_audit.py -v
```
Expected: **4 passed, 0 failed**.

---

## 39. YAML Safe Loading (TASK-039)

**Files changed:** `phase3_pipeline/categorizer.py`, `phase3_pipeline/category_loader.py`, `phase3_pipeline/profile_manager.py`

**Files added:** `backend/local/yaml_safe.py`, `backend/tests/test_yaml_safety.py`

**Changes:**
- Centralized YAML loading in `backend/local/yaml_safe.py` using `CSafeLoader` when available and `SafeLoader` as fallback.
- Replaced direct `yaml.safe_load(f)` calls in `phase3_pipeline` with `safe_load_yaml_file()`.
- Added project-wide static test banning `yaml.load(...)` calls without an explicit `Loader=` kwarg.
- Added pre-commit hook (or CI documentation) to prevent future unsafe YAML loading regressions.

**Verification:**
```bash
python -m pytest backend/tests/test_yaml_safety.py -v
```
Expected: **4 passed, 0 failed**.

---

*Draft ready for copy-paste into CHANGES.md once the security sprint test suite is green.*
