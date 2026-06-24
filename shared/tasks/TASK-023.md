# TASK-023: Dependency Vulnerability Scanning

## Metadata
- **Project:** TaxFlow Pro v3.9.2
- **Assigned by:** James Clawd (orchestrator)
- **Status:** COMPLETE
- **Completed:** 2026-06-21

## Objective
Provide an offline dependency vulnerability scanner that checks installed Python packages against a local vulnerability database without sending data to external APIs.

## Deliverables

### 1. `backend/security/vuln_scanner.py`
New module with:
- `scan_dependencies(vuln_db_path)` — maps installed distributions against a JSON vulnerability database.
- `format_report(matches)` — returns a JSON-serializable `{ok, vulnerable_count, matches}` dict.
- Supports OSV-style ranges and simple affected-version strings.
- Version comparison uses normalized integer tuples.

### 2. `scripts/vuln_scan.py`
CLI entry point:
- Default DB: `data/vuln-db.json`.
- Writes JSON report to stdout or `--output` path.
- Exit codes: `0` (clean), `1` (vulns detected), `2` (scanner error).
- Adds project root to `sys.path` so it works from `scripts/`.

### 3. `data/vuln-db.json`
Sample offline vulnerability database in OSV-compatible format covering `requests`, `fastapi`, and `cryptography`.

### 4. `backend/tests/test_vuln_scanner.py`
Tests for version parsing/range matching, installed-package detection, fixed-version skipping, and report formatting.

### 5. `.env.example`
Added `TAXFLOW_VULN_DB_PATH=data/vuln-db.json`.

### 6. `README.md`
Added Security Scanning section documenting the offline dependency scanner.

## Test Results
- `pytest backend/tests/test_vuln_scanner.py -v` → **8 passed, 0 failed**
- CLI smoke test: `python scripts/vuln_scan.py --db data/vuln-db.json --output vuln_report.json` → `{ok: true, vulnerable_count: 0}`

## Files Changed
- `backend/security/vuln_scanner.py` (new)
- `scripts/vuln_scan.py` (new)
- `data/vuln-db.json` (new)
- `backend/tests/test_vuln_scanner.py` (new)
- `.env.example`
- `README.md`

## Verification Steps
```bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
python -m pytest backend/tests/test_vuln_scanner.py -v
python scripts/vuln_scan.py --db data/vuln-db.json
```

## Notes
- No network calls; scanner works in offline mode.
- No new runtime dependencies.
- No commit made; v3.9.2 batched commit pending.
