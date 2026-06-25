# TASK-3.10.S13 — DoS Limits on Uploads

**Owner:** TBD  
**Goal:** Cap file size, page count, and transaction count to prevent abuse.

## Files

- `backend/routers/upload.py`
- `backend/parsers/generic_pdf.py`
- `backend/tests/test_upload_limits.py`

## Requirements

1. Max PDF file size (e.g., 50 MB).
2. Max pages per PDF (e.g., 500).
3. Max transactions per import (e.g., 10,000).
4. Return clear 413/422 errors.

## Tests

- Oversized file rejected.
- Too many pages rejected.
- Too many transactions rejected.
- Normal file passes.

## Report

Files changed, limit values, test results.
