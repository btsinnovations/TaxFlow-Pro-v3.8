# TASK-3.10.S01 — Path Traversal Protection

**Owner:** TBD  
**Goal:** Prevent path traversal in file upload and export endpoints.

## Files

- `backend/routers/upload.py`
- `backend/routers/export.py`
- `backend/utils/paths.py`
- `backend/tests/test_path_traversal.py`

## Requirements

1. Reject filenames containing `..`, absolute paths, or null bytes.
2. Store uploaded files by generated UUID in a flat uploads directory.
3. Export filenames are sanitized to a safe basename.

## Tests

- Filename `../../etc/passwd` rejected.
- Filename `file\x00.exe` rejected.
- Export filename with traversal sanitized.
- Normal filename accepted.

## Report

Files changed, sanitization rules, test results.
