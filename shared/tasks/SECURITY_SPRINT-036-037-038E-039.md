# Security Hardening Sprint — TASK-036, 037, 038-Entropy, 039

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Sprint goal:** Close the four remaining v3.9.2 security hardening tasks in one coordinated pass.

---

## Why a sprint instead of separate tasks

All four tasks touch the same areas:
- Local settings / secrets handling
- Dependency and audit hygiene
- Static analysis / linting
- `CHANGES.md` release notes

By batching them, you can reuse helpers, avoid duplicated test setup, and produce a single clean commit.

---

## Execution order

1. **TASK-036** — Secrets file support + URL redaction.
2. **TASK-037** — Dependency confusion mitigation (`pyproject.toml`, lockfile, namespace policy).
3. **TASK-038-Entropy-Audit** — Replace `random` with `secrets` in security paths.
4. **TASK-039** — Centralized safe YAML loader + lint.
5. **Final** — Full test suite + CHANGES.md consolidation.

---

## Starter modules already scaffolded

The orchestrator created these files for you to extend:

- `backend/local/secrets_loader.py` — load `TAXFLOW_SECRETS_FILE` key=value pairs.
- `backend/local/security_random.py` — `secure_token`, `secure_urlsafe_token`, `secure_random_int`, `secure_alphanumeric`.
- `backend/local/yaml_safe.py` — `safe_load_yaml`, `safe_load_yaml_file` with `CSafeLoader` fallback.
- `pyproject.toml` — non-publishable project metadata placeholder.

You may modify them as needed.

---

## Pre-audit findings

See `audit_output/security_sprint_findings.md` for:
- Entropy audit hits (none found in security-critical modules; minor `random` usage detected for review).
- YAML loading audit (all current uses are `safe_load`; no regression risk).
- Dependency status (no internal packages yet; lockfile needed).

Use the findings to target your changes rather than starting from scratch.

### Orchestrator pre-checks completed (2026-06-23)
- Entropy: `Select-String` across `backend/`, `backend/routers/`, and `backend/local/` found **no** `import random` or `from random`. Current security paths already use `secrets`. The remaining TASK-038-Entropy work is to add tests and annotate any non-security `random` usage (e.g., fuzz tests, sample data generators).
- `encryption_salt=None` fixture gap: `backend/local/crypto.py::LocalCryptoManager.from_stored` currently falls back to a deterministic test salt `b"taxflow-test-salt-16"` when `salt_b64` is None. The Security Sprint must:
  1. Update `backend/tests/conftest.py` to generate a real random salt instead of passing `encryption_salt=None`.
  2. Remove the deterministic fallback in `from_stored` so it raises `EncryptionError` on `None`/empty salt.
- YAML safety: all current `yaml.load` calls use `SafeLoader` or `safe_load`; TASK-039 is a migration + regression test, not a bug-fix pass.

---

## TASK-036 — Sensitive Data in Process Arguments

### Files to change
- `backend/local/settings.py` — import and use `secrets_loader`.
- `backend/database.py` — import `_SECRETS` from settings for `DATABASE_URL`.
- `.env.example` — add `TAXFLOW_SECRETS_FILE` guidance.

### Files to add
- `backend/local/secrets_loader.py` (already scaffolded).
- `backend/tests/test_secret_handling.py`.

### Acceptance
- `TAXFLOW_SECRETS_FILE` overrides env for `DATABASE_URL`, `TAXFLOW_DB_PASSWORD`, `TAXFLOW_DB_KEYFILE`, `TAXFLOW_DB_KEYRING_TOKEN`.
- `redact_url()` removes password from logged URLs.
- Tests pass.

---

## TASK-037 — Dependency Confusion Mitigation

### Files to change
- `README.md` or `BUILDER_MANUAL.md` — document internal package namespace policy.
- `.pre-commit-config.yaml` (if exists) — add lockfile check.

### Files to add
- `pyproject.toml` (already scaffolded).
- `requirements-lock.txt` — pinned versions with hashes if `pip-tools` available; exact versions otherwise.
- `backend/tests/test_dependency_confusion.py`.

### Acceptance
- `pyproject.toml` name is non-publishable.
- Lockfile exists and covers all `requirements.txt` top-level packages.
- Test asserts lockfile presence and pinned versions.

---

## TASK-038-Entropy-Audit — Weak Entropy Audit

### Files to change
- Any security-critical module still using `random` (see findings report).
- Replace with `backend.local.security_random` helpers.

### Files to add
- `backend/local/security_random.py` (already scaffolded).
- `backend/tests/test_entropy_audit.py`.

### Acceptance
- `backend/auth.py`, `backend/local/crypto.py`, `backend/local/keyring_secret.py`, `backend/routers/auth.py` do not import `random`.
- `secure_token`, `secure_random_int`, `secure_urlsafe_token` tested.
- Non-security `random` usage is commented `# NON-SECURITY` or `# TEST-ONLY`.

---

## TASK-039 — YAML Safe Loading

### Files to change
- `phase3_pipeline/categorizer.py` — use `safe_load_yaml_file`.
- `phase3_pipeline/category_loader.py` — use `safe_load_yaml_file`.
- `phase3_pipeline/profile_manager.py` — use `safe_load_yaml_file`.

### Files to add
- `backend/local/yaml_safe.py` (already scaffolded).
- `backend/tests/test_yaml_safety.py`.

### Acceptance
- No direct `yaml.load(...)` without explicit Loader.
- `CSafeLoader` used when available.
- Test bans unsafe `yaml.load` calls project-wide.

---

## CHANGES.md sections

The orchestrator drafted Sections 36, 37, 38, and 39 in `audit_output/security_sprint_changes_draft.md`. Review, correct, and copy them into `CHANGES.md` after the tasks pass.

---

## Final verification

Run this sequence and report results:

```bash
python -m pytest backend/tests/test_secret_handling.py -q
python -m pytest backend/tests/test_dependency_confusion.py -q
python -m pytest backend/tests/test_entropy_audit.py -q
python -m pytest backend/tests/test_yaml_safety.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

---

## Constraints

- No new production dependencies.
- No gateway restart / OpenClaw config changes.
- Backward compatible: env vars still work.
- Report blockers via `sessions_send`.

Start this sprint when you have finished the TASK-038.x Phase 3 Foundation queue.
