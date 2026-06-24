# TASK-028 — Global Rate Limiting

**Status:** COMPLETE  
**Completed:** 2026-06-21 (EDT)  
**Assignee:** Jane Clawd

## Objective
Add a global, per-IP sliding-window rate limiter that applies to **all** requests before authentication and tenant handling, with safe behavior behind proxies and a bypassable reset for tests.

## Implementation

### New file: `backend/rate_limit.py`
- `GlobalRateLimiter`
  - Per-IP sliding windows with configurable `limit`, `window`, and `burst`.
  - `from_env()` reads:
    - `TAXFLOW_GLOBAL_RATE_LIMIT` (default `100/minute`)
    - `TAXFLOW_GLOBAL_BURST_LIMIT` (default `10`)
    - `TAXFLOW_TRUSTED_PROXY_HOPS` (default `0`)
- `_parse_limit()` supports `N/UNIT` and `N/MULTIPLIER UNIT` for `second`, `minute`, `hour`, `day`.
- Client IP detection:
  - If `trusted_proxy_hops == 0`, uses direct `remote_addr` and ignores `X-Forwarded-For` (prevents spoofing).
  - If `>0`, extracts the client IP from `X-Forwarded-For` at index `-(trusted_proxy_hops + 1)`.
- Exceeded requests raise `HTTPException(429)` with `Retry-After` header.

### Updated: `backend/api.py`
- Added `_GlobalRateLimitMiddleware` mounted very early in the middleware stack.
- Converts rate-limit `HTTPException` into a `JSONResponse(429)` with `Retry-After` so it behaves correctly as a `BaseHTTPMiddleware`.
- Exposes a module-level `_GLOBAL_RATE_LIMITER` singleton instantiated via `GlobalRateLimiter.from_env()`.

### Updated: `.env.example`
- Added `TAXFLOW_GLOBAL_RATE_LIMIT`, `TAXFLOW_GLOBAL_BURST_LIMIT`, `TAXFLOW_TRUSTED_PROXY_HOPS`.

### Updated: `README.md`
- Added new env vars to the configuration table.
- Added a "Rate Limiting" section documenting defaults, trusted proxies, and the separate auth brute-force protection.

### New test file: `backend/tests/test_global_rate_limit.py`
- 9 tests covering:
  - default volume allowance
  - tight-limit rejection (429 + `Retry-After`)
  - window expiry / retry-after timing
  - `X-Forwarded-For` handling with and without trusted hops
  - rate-limit string parsing and invalid-format rejection
  - env overrides for rate limit and proxy hops
- Autouse fixture resets `_GLOBAL_RATE_LIMITER` to a clean default before/after each test to avoid cross-test contamination.

## Test Results
- `pytest backend/tests/test_global_rate_limit.py -v` → **9 passed, 0 failed**
- Targeted regression (rate limits + security headers + API + hybrid auth) → **57 passed, 0 failed**
- Full backend suite `pytest backend/tests -q` → **246 passed, 0 failed**

## Files Changed
- `backend/rate_limit.py` (new)
- `backend/api.py` (middleware + `_GLOBAL_RATE_LIMITER`)
- `.env.example`
- `README.md`
- `backend/tests/test_global_rate_limit.py` (new)
- `backend/tests/test_security_headers.py` (reset limiter in reload-sensitive tests)
