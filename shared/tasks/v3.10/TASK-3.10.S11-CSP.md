# TASK-3.10.S11 — CSP + localStorage Hardening

**Owner:** TBD  
**Goal:** Add CSP headers and secure localStorage/sessionStorage handling.

## Files

- `backend/api.py`
- Frontend API client
- `frontend/src/lib/auth.ts`
- `backend/tests/test_csp.py`

## Requirements

1. Serve CSP headers appropriate for a local Vite app.
2. localStorage token keys use predictable names.
3. Token cleared on logout and app lock.

## Tests

- CSP header present.
- Token removed from localStorage on logout.

## Report

Files changed, CSP policy, test results.
