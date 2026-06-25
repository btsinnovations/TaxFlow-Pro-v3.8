# TASK-3.10.S05 — Dependency Confusion Mitigation

**Owner:** TBD  
**Goal:** Prevent internal package names from being squatted on public indexes.

## Files

- `pyproject.toml`
- `.pypirc` / `pip.conf` template
- `backend/tests/test_dependency_names.py`

## Requirements

1. Audit internal module names against PyPI.
2. Pin all dependencies with hashes where possible.
3. Document internal registry or `--index-url` policy.

## Tests

- No internal package name exists on PyPI.
- Requirements file uses hashes or explicit index.

## Report

Audit findings, files changed, policy doc.
