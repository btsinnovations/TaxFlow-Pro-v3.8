# Security Sprint Pre-Audit Findings

Generated: 2026-06-23 07:00 EDT
Scope: backend/, phase3_pipeline/, scripts/

---

## TASK-036 — Sensitive Data in Process Arguments

### Findings

- `backend/database.py` reads `DATABASE_URL` from `os.environ` only. No secrets-file fallback exists.
- `backend/local/settings.py` reads `TAXFLOW_DB_PASSWORD`, `TAXFLOW_DB_KEYFILE`, `TAXFLOW_DB_KEYRING_TOKEN` from `os.environ` only.
- `start.sh` does not pass `DATABASE_URL` on the command line, but it is sourced from the environment.
- No `TAXFLOW_SECRETS_FILE` support exists.
- No `redact_url()` helper exists for logging.
- No evidence of `DATABASE_URL` or passwords being printed/logged was found in a quick scan, but no lint enforces this.

### Recommended actions

1. Add `backend/local/secrets_loader.py` (already scaffolded).
2. Update `backend/local/settings.py` to use `get_secret()` for sensitive keys.
3. Update `backend/database.py` to use `get_secret("DATABASE_URL", ...)`.
4. Add `redact_url()` and use it anywhere `DATABASE_URL` is logged.
5. Add tests in `backend/tests/test_secret_handling.py`.

---

## TASK-037 — Dependency Confusion Mitigation

### Findings

- No `pyproject.toml` exists yet.
- `requirements.txt` uses version ranges (`>=`) for many packages.
- No `requirements-lock.txt` with hashes exists.
- No internal Python packages are referenced, so no active confusion risk.
- `frontend/package-lock.json` exists; npm side is reasonably pinned.
- No documented namespace policy for future internal packages.

### Recommended actions

1. Add `pyproject.toml` with non-publishable name `taxflow-pro-private` (already scaffolded).
2. Generate `requirements-lock.txt` with pinned versions and hashes if `pip-tools` available; exact versions as fallback.
3. Add namespace policy to `README.md` or `BUILDER_MANUAL.md`.
4. Add `backend/tests/test_dependency_confusion.py`.
5. Optional: add pre-commit hook for lockfile presence.

---

## TASK-038-Entropy-Audit — Weak Entropy Audit

### Findings

- No `import random` or `from random import ...` was found in `backend/`, `phase3_pipeline/`, or `scripts/`.
- `backend/local/auth.py` uses `import secrets`.
- `backend/local/crypto.py` uses `import secrets`.
- `backend/local/sqlcipher_engine.py` uses `import secrets`.
- No `uuid.uuid1()` usage found.
- No `numpy.random` usage found outside of potential ML paths (ML training is considered non-security).
- The word "random" appears only in docstrings/comments/test strings, not as stdlib `random` usage.

### Recommended actions

1. Add `backend/local/security_random.py` with helper functions (already scaffolded).
2. Add `backend/tests/test_entropy_audit.py` to enforce that security-critical modules never import `random`.
3. If future code adds `random`, the test will fail and force a disposition.
4. Mark any non-security random usage with `# NON-SECURITY` or `# TEST-ONLY` comments.

---

## TASK-039 — YAML Safe Loading

### Findings

- `phase3_pipeline/categorizer.py:24` — `yaml.safe_load(f)` ✅
- `phase3_pipeline/category_loader.py:31` — `yaml.safe_load(f)` ✅
- `phase3_pipeline/profile_manager.py:32` — `yaml.safe_load(f)` ✅
- No `yaml.load(...)` calls without an explicit Loader found.
- No `yaml.unsafe_load` or `yaml.FullLoader` usage found.
- No centralized helper exists.
- `CSafeLoader` is not explicitly requested.

### Recommended actions

1. Add `backend/local/yaml_safe.py` with `CSafeLoader`/SafeLoader fallback (already scaffolded).
2. Update the three `phase3_pipeline` loaders to use `safe_load_yaml_file`.
3. Add `backend/tests/test_yaml_safety.py` including a project-wide static check.
4. Add pre-commit hook or CI check banning `yaml.load(...)` without explicit `Loader=`.

---

## Summary

No active security regressions found. The main work is defensive:
- Add scaffolding that prevents future mistakes (centralized helpers, tests, lockfiles).
- Document namespace and secrets-file policies.
- Ensure all current safe practices are enforced by tests and CI.
