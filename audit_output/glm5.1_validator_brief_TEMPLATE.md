# glm-5.1 Validator Brief Template

## Purpose
This brief is sent to the `glm-5.1` validator session after the v3.10 implementation is complete. It provides the validator with scope, entry points, and success criteria so the review is efficient and deterministic.

## Scope to validate

### Code changes since last validated baseline
- All files under `backend/local/` (settings, secrets, crypto, auth, backup, bootstrap, yaml_safe, security_random, etc.)
- All files under `backend/routers/`
- `backend/api.py`, `backend/database.py`, `backend/rls.py`, `backend/auth.py`
- `backend/tests/test_*.py` security-related suites
- `scripts/dependency_audit.py`, `scripts/sast_scan.py`, `scripts/sbom_generate.py`, `scripts/secret_scan.py`
- `pyproject.toml`, `requirements-lock.txt`, `requirements.txt`

### Security properties to verify
1. **No secrets in process arguments.** `DATABASE_URL` password and SQLCipher secrets are loaded from `TAXFLOW_SECRETS_FILE` or keyring, not `os.environ` in production paths.
2. **No weak entropy.** No `random` module usage in security-critical paths. Tokens, salts, nonces use `secrets`.
3. **Safe YAML loading.** All YAML parsing uses `backend.local.yaml_safe` with `CSafeLoader`/`SafeLoader`.
4. **Dependency confusion mitigated.** Internal package names are non-publishable (`taxflow-pro-private`). Lockfile covers top-level deps.
5. **Single-user default secure.** SQLite mode ignores `X-Tenant-ID`; multi-entity PostgreSQL requires it.
6. **Column encryption robust.** `encryption_salt=None` fixture gap removed; salt always present and non-deterministic.
7. **Audit trail tamper-evident.** Hash chain + append-only triggers active.
8. **Cloud calls blocked in offline mode.** `guard_cloud_call` and `FEATURE_FLAGS` prevent Plaid/STMP/OAuth/telemetry.
9. **Local server binds to 127.0.0.1** by default; LAN bind is opt-in.
10. **Build packaging for v3.10** bundles interpreter, frontend, Tesseract/Poppler, and uses writable user data dir.

## Validation commands

```bash
# Security-focused suites
python -m pytest backend/tests/test_secret_handling.py backend/tests/test_dependency_confusion.py backend/tests/test_entropy_audit.py backend/tests/test_yaml_safety.py backend/tests/test_single_user_mode.py backend/tests/test_rls.py backend/tests/test_crypto.py -q

# Full regression
python -m pytest backend/tests tests -q

# Static scans
python scripts/sast_scan.py
python scripts/secret_scan.py
python scripts/dependency_audit.py
python scripts/sbom_generate.py
```

## Expected results
- All focused suites pass with 0 failures.
- Full regression passes with 0 failures.
- Static scans report no high/critical issues.
- SBOM is generated and non-empty.

## Files to produce
- `audit_output/glm5.1_review_report.md` — findings, risk ratings, recommendations.

## Decision gates
- **Pass:** 0 high/critical findings, all tests green.
- **Conditional pass:** Minor findings with documented compensating controls.
- **Fail:** Any high/critical security finding or test failure. Fix and re-run.
