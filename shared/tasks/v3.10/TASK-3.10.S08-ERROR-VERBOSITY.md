# TASK-3.10.S08 — Error Verbosity Sanitization

**Owner:** TBD  
**Goal:** Ensure production mode never returns stack traces or internal paths in API responses.

## Files

- `backend/api.py`
- `backend/main.py`
- Exception handlers
- `backend/tests/test_error_sanitization.py`

## Requirements

1. Global exception handler returns generic error in production.
2. Stack traces and file paths logged internally only.
3. Development mode may return detailed errors.

## Tests

- Production endpoint raises 500 → response contains no file paths or tracebacks.
- Internal log still captures full traceback.

## Report

Files changed, environment handling, test results.
