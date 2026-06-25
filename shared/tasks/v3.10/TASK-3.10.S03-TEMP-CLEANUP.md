# TASK-3.10.S03 — Temporary File Cleanup

**Owner:** TBD  
**Goal:** Ensure uploaded PDFs, OCR images, and exports are cleaned up after processing.

## Files

- `backend/parsers/generic_pdf.py`
- `backend/routers/upload.py`
- `backend/routers/export.py`
- `backend/tests/test_temp_cleanup.py`

## Requirements

1. Use `tempfile.TemporaryDirectory` or explicit cleanup in `finally` blocks.
2. Remove uploaded PDF after extraction if configured.
3. Audit `uploads/` for stale files.

## Tests

- Temp files deleted after successful import.
- Temp files deleted after failed import.
- `uploads/` does not grow unbounded across test runs.

## Report

Files changed, cleanup strategy, audit results.
