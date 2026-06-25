# TASK-3.10.T08 — pikepdf PDF Sanitization

**Owner:** TBD  
**Goal:** Pre-process uploaded PDFs with pikepdf to strip JavaScript, embedded files, and malformed structures before parsing.

## Files

- `backend/services/pdf_sanitize.py`
- `backend/routers/upload.py`
- `backend/parsers/generic_pdf.py`
- `backend/tests/test_pikepdf_sanitize.py`

## Requirements

1. Use `pikepdf` to open and rewrite PDFs.
2. Remove `/JavaScript`, `/Names/EmbeddedFiles`, actions, and launch commands.
3. Reject encrypted PDFs or require password first.
4. Preserve text extractability.

## Tests

- Malicious PDF stripped clean.
- Normal statement PDF passes and text extraction still works.
- Encrypted PDF rejected or handled safely.

## Report

Files changed, sanitization rules, test results.
