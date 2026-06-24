# TASK-021: PDF Upload Validation

## Metadata
- **Project:** TaxFlow Pro v3.9.2
- **Assigned by:** James Clawd (orchestrator)
- **Deadline:** 2026-06-21 22:00 America/New_York
- **Status:** COMPLETE
- **Completed:** 2026-06-21

## Objective
Harden the `/api/upload` endpoint so only valid, reasonably sized PDF files are accepted. Reject malicious or mislabeled uploads before they are written to disk or parsed.

## Deliverables

### 1. `backend/security/upload_validator.py`
New module providing `validate_upload_file(file, filename)` with checks for:
- File extension whitelist (`.pdf` only) — HTTP 415.
- Declared MIME type (`application/pdf`) — HTTP 415.
- Size limit (`TAXFLOW_MAX_UPLOAD_BYTES`, default 32 MiB) — HTTP 413.
- PDF magic header (must start with `%PDF-`) — HTTP 415.
- Optional strict mode (`TAXFLOW_UPLOAD_MAGIC_STRICT=true`) requiring PDF version 1.x or 2.x.

Returns validated file bytes for downstream use.

### 2. Updated `backend/routers/upload.py`
The `upload_statement` route now calls `validate_upload_file(file, file.filename)` immediately and passes the validated bytes to `store_uploaded_file()`. The file is rejected before any parser or database access occurs.

### 3. Request size limit in `backend/api.py`
Added `_RequestSizeLimitMiddleware` (Starlette `BaseHTTPMiddleware`) that inspects the `Content-Length` header and returns HTTP 413 if the request body exceeds `MAX_UPLOAD_SIZE_BYTES`. This catches oversized requests before they reach the upload router.

### 4. `backend/tests/test_upload_security.py`
New test suite covering:
- Valid PDF passes validation.
- Oversized PDF rejected (413).
- Wrong extension rejected (415).
- Wrong MIME type rejected (415).
- Fake extension / no magic bytes rejected (415).
- Empty file rejected (415).
- Authenticated endpoint tests for valid, oversized, wrong extension, and fake magic-byte uploads.

### 5. Updated `.env.example`
Added:
```
TAXFLOW_MAX_UPLOAD_BYTES=33554432
TAXFLOW_UPLOAD_MAGIC_STRICT=false
```

### 6. Updated `README.md`
Added an **Upload** section documenting PDF-only uploads, size limit, strict mode, and that rejected files are never written to the parser temp directory.

### 7. Updated `backend/tests/test_api.py`
`test_upload_rejects_non_pdf` now expects HTTP 415 (matching the new validator) and checks for the "Only PDF" message.

## Test Results
- `pytest backend/tests/test_upload_security.py -v` → **10 passed, 0 failed**
- `pytest backend/tests/test_api.py backend/tests/test_upload_security.py -v` → **23 passed, 0 failed**
- Combined targeted run including backup/restore, audit trail, keyring, hybrid auth, and API tests → **69 passed, 0 failed**

## Files Changed
- `backend/security/upload_validator.py` (new)
- `backend/routers/upload.py`
- `backend/api.py`
- `backend/tests/test_upload_security.py` (new)
- `backend/tests/test_api.py`
- `.env.example`
- `README.md`

## Notes
- No commit per project instructions; v3.9.2 changes remain batched for a single commit.
- The endpoint test for a valid PDF creates a test `Client` and `Account` so the upload can be persisted without hitting unrelated `tenant_id` NOT NULL constraints.
- Combined test run completed successfully with no regressions.

## Verification Steps
```bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
python -m pytest backend/tests/test_upload_security.py -v
python -m pytest backend/tests/test_api.py backend/tests/test_upload_security.py -v
```
