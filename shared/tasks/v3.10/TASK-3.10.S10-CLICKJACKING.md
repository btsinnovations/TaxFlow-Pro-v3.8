# TASK-3.10.S10 — Clickjacking / Frame Protection

**Owner:** TBD  
**Goal:** Prevent the localhost app from being embedded in a malicious iframe.

## Files

- `backend/api.py`
- `backend/middleware/security_headers.py`
- `backend/tests/test_frame_options.py`

## Requirements

1. Add `X-Frame-Options: DENY`.
2. Add `Content-Security-Policy: frame-ancestors 'none'`.
3. Apply to all responses.

## Tests

- Headers present on API responses.
- Frontend cannot be embedded in iframe.

## Report

Files changed, header values, test results.
