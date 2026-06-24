# TASK-027: TaxFlow Pro v3.9.2 — Security Headers + CORS Hardening

## Status
**COMPLETE** — implementation, tests, and full regression all green.

## Goal
Harden CORS policy and add baseline security headers to all HTTP responses.

## Implementation Details
- `backend/api.py`:
  - Added `_get_cors_origins()` helper reading `TAXFLOW_CORS_ORIGINS` (comma-separated) with safe defaults for local dev ports.
  - Replaced wildcard `allow_methods=["*"]` and `allow_headers=["*"]` with explicit allow-lists:
    - Methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
    - Headers: `authorization`, `content-type`, `x-tenant-id`, `x-requested-with`.
    - Exposed headers: `x-request-id`.
    - `max_age=600`.
  - Added `_SecurityHeadersMiddleware` (`BaseHTTPMiddleware`) setting:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()`
    - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`
    - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (production only, controlled by `TAXFLOW_ENVIRONMENT=production`).
- `.env.example`:
  - Added `TAXFLOW_ENVIRONMENT=development`.
  - Added `TAXFLOW_CORS_ORIGINS` defaulting to local dev origins.
  - Removed duplicate Security section.
- `README.md`:
  - Configuration table updated with `TAXFLOW_ENVIRONMENT` and `TAXFLOW_CORS_ORIGINS`.
  - Added note that HSTS is enabled only in production.
- `backend/tests/test_security_headers.py` (new):
  - 9 tests covering:
    - Allowed-origin preflight and GET.
    - Disallowed-origin preflight rejection (400) and no CORS headers on GET.
    - Security headers on `/health` and `/api/health`.
    - HSTS absent in development.
    - HSTS present in production.
    - `TAXFLOW_CORS_ORIGINS` env override behavior.

## Test Results
- `pytest backend/tests/test_api.py backend/tests/test_security_headers.py backend/tests/test_hybrid_auth.py -v`: **48 passed, 0 failed**.
- `pytest backend/tests -q`: **237 passed, 0 failed**.

## Security Properties
- CORS credentials are only sent to explicitly configured origins.
- No wildcard methods or headers; the attack surface for CORS-based token exfiltration is reduced.
- Clickjacking is blocked via `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'`.
- MIME sniffing is disabled via `X-Content-Type-Options: nosniff`.
- HSTS is opt-in via `TAXFLOW_ENVIRONMENT=production`, preventing accidental HTTPS enforcement during local development.

## Notes
- No commit yet per orchestrator instruction; all v3.9.2 changes remain batched for the v3.9.2 release.
- Next task: **TASK-028: Global rate limiting**.
