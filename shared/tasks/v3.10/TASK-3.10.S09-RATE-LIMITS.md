# TASK-3.10.S09 — API Rate Limiting Beyond Login

**Owner:** TBD  
**Goal:** Add per-user rate limiting on upload, export, and ML training endpoints.

## Files

- `backend/middleware/rate_limit.py` or in-router decorators
- `backend/routers/upload.py`
- `backend/routers/export.py`
- `backend/routers/training.py`
- `backend/tests/test_rate_limits.py`

## Requirements

1. In-memory sliding-window rate limiter.
2. Separate limits for upload, export, training.
3. Return 429 with `Retry-After` when exceeded.

## Tests

- Burst within limit succeeds.
- Burst over limit returns 429.
- Limits reset after window.

## Report

Files changed, limit values, test results.
