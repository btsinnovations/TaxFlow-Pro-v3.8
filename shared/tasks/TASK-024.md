# TASK-024: Secret Scanning in CI / Pre-commit

## Metadata
- **Project:** TaxFlow Pro v3.9.2
- **Assigned by:** James Clawd (orchestrator)
- **Status:** IN PROGRESS
- **Started:** 2026-06-21

## Objective
Add an offline secret scanner that runs locally in CI / pre-commit to catch potential secrets in source files without uploading anything to external APIs.

## Deliverables (planned)

### 1. `scripts/secret_scan.py`
CLI scanner for:
- High-confidence secret-like line regex (`api_key`, `secret_key`, `password`, etc.).
- Broad keyword pattern matches with allowlisting.
- Placeholder / test-value detection to reduce false positives.
- JSON and plain-text output modes.
- Configurable patterns via `TAXFLOW_SECRET_PATTERNS` and fail-on-finding via `TAXFLOW_SECRET_SCAN_FAIL`.

### 2. `.pre-commit-config.yaml`
Add a local pre-commit hook running `python scripts/secret_scan.py --fail` on every commit.

### 3. `backend/tests/test_secret_scan.py`
Unit tests covering flagging real-looking secrets, ignoring placeholders, allowlisting, binary skipping, JSON mode, and fail behavior.

### 4. `.env.example` / `README.md`
Document `TAXFLOW_SECRET_PATTERNS` and `TAXFLOW_SECRET_SCAN_FAIL`.

## Notes
- Scanner is intentionally conservative; it flags suspicious patterns for human review.
- No network calls.
- No commit made; v3.9.2 batched commit pending.
