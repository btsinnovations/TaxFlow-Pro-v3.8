# TASK-029 — Password Breach Bloom Filter

**Status:** COMPLETE  
**Completed:** 2026-06-21 (EDT)  
**Assignee:** Jane Clawd

## Objective
Detect passwords that appear in known breach corpora during boot/registration/change-password without adding an external dependency or making network calls.

## Implementation

### New file: `backend/security/breach_bloom.py`
- Dependency-free, JSON-serializable counting Bloom filter.
- Configurable capacity and false-positive rate.
- Built-in `TAXFLOW_BREACH_BLOOM_PATH` env var support.
- SHA-256-derived hash slices; supports save/load to JSON.
- Tiny built-in common-password list when no external bloom filter is configured.

### New file: `scripts/build_bloom_filter.py`
- CLI that builds a bloom filter from a newline-delimited password list.
- Configurable `--capacity` and `--fpr`.
- Output JSON consumed by `backend/security/breach_bloom.py`.

### Updated: `backend/utils/password_policy.py`
- Imports `is_breached()` from `backend.security.breach_bloom`.
- Adds a policy failure: `Password appears in a known breach database.`

### Updated: `.env.example`
- Added `TAXFLOW_BREACH_BLOOM_PATH`.

### Updated: `README.md`
- Added `TAXFLOW_BREACH_BLOOM_PATH` to the configuration table.
- Added a "Password policy" subsection under Authentication listing the breach-bloom check.

### New test file: `backend/tests/test_breach_bloom.py`
- 8 tests covering:
  - basic add/membership
  - JSON save/load round-trip
  - default built-in filter behavior
  - env override via `TAXFLOW_BREACH_BLOOM_PATH`
  - missing env path falls back to default
  - boot endpoint rejects a breached password
  - boot endpoint accepts a non-breached password
  - builder script in-process

## Test Results
- `pytest backend/tests/test_breach_bloom.py -v` → **8 passed, 0 failed**
- Targeted regression (breach bloom + rate limits + security headers + hybrid auth + API) → **65 passed, 0 failed**
- Full backend suite `pytest backend/tests -q` → **254 passed, 0 failed**

## Files Changed
- `backend/security/breach_bloom.py` (new)
- `scripts/build_bloom_filter.py` (new)
- `backend/utils/password_policy.py`
- `.env.example`
- `README.md`
- `backend/tests/test_breach_bloom.py` (new)

## Notes
- No new runtime dependency; implemented in pure Python.
- Production deployments should generate a real filter from a large breach corpus using `scripts/build_bloom_filter.py`.
- No commit per instruction; v3.9.2 batched commit pending.
