# TASK-3.10.S15 — Frontend Dependency Supply Chain

**Owner:** TBD  
**Goal:** Pin and audit npm dependencies to reduce supply-chain risk.

## Files

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tests/test_npm_audit.py`

## Requirements

1. Pin exact versions in `package.json`.
2. Run `npm audit` and fix or document high/critical findings.
3. Add pre-commit or CI check for `npm audit`.

## Tests

- `npm audit` returns zero high/critical vulnerabilities or documented exceptions.
- Build still passes after pinning.

## Report

Files changed, audit results, exceptions documented.
