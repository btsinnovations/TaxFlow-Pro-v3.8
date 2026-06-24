# Cloud Code Audit (TASK-038.6)

**Date:** 2026-06-22  
**Scope:** `backend/`, `frontend/src/`, `scripts/`  
**Goal:** Identify and gate/remove any imports or network calls that could "phone home" in offline/default mode.

---

## Executive Summary

TaxFlow Pro v3.9.1 is designed as a local-first application. The audit found **no hardcoded cloud API calls or telemetry** in runtime code. The only network surface area is:

1. The frontend `fetch` calls to the **locally-hosted** FastAPI backend (`http://localhost:8000/api` by default).
2. `frontend/index.html` loads Google Fonts from `https://fonts.googleapis.com` and `https://fonts.gstatic.com` (UI-only, not runtime data).

All Plaid, Stripe, SMTP, OAuth, telemetry, and auto-update-check features are **already disabled by default** in `backend/local/settings.py` (`FEATURE_FLAGS`). No backend router attempts to reach the public internet in the default offline runtime mode.

---

## Methodology

Automated scans searched `backend/`, `frontend/src/`, and `scripts/` for:

- `requests` / `urllib` / `http.client` imports and calls
- Raw `socket.create_connection` / `socket.connect` usage
- Plaid, Stripe, Twilio, SendGrid, SMTP, Sentry, OAuth, OpenID references
- Telemetry / analytics keywords (Segment, Mixpanel, Amplitude, Google Analytics, PostHog, etc.)
- Update-check/version-check patterns
- `fetch`, `axios`, `@apollo`, external `https://` URLs in frontend source

Each match was manually inspected to confirm whether it represented a genuine network path.

---

## Findings

### Backend

| File / Pattern | Finding | Disposition |
|---|---|---|
| `backend/local/settings.py` | `FEATURE_FLAGS` already disable `plaid`, `stripe`, `smtp_email`, `oauth_login`, `telemetry`, `auto_update_check`, `cloud_ml`. | ✅ Already gated |
| `backend/auth.py`, `backend/local/auth.py`, `backend/routers/auth.py` | `oauth2_scheme` from FastAPI is used for local JWT bearer-token parsing only. No OAuth provider calls. | ✅ Local-only convention |
| `backend/local/offline.py` | Contains `_has_network_access()` probe used only by offline self-tests. It never initiates outbound calls on behalf of user data. | ✅ Diagnostic-only |
| `backend/local/guards.py` | Contains socket-related helpers for network lockdown (no outbound calls). | ✅ Hardening, not leakage |
| `backend/parsers/generic_pdf.py` | Merchant regex includes `STRIPE` as a payment-processor keyword, not a Stripe API call. | ✅ Keyword match only |
| `scripts/generate_graveyard.py` | Graveyard fixture data contains "STRIPE PAYOUTS" as sample transaction text. | ✅ Static fixture only |
| `backend/security/upload_validator.py` | PDF-version check string triggered the "update_check" regex ("strict version check"). No network. | ✅ False positive |
| `backend/tests/test_local_first.py` | Contains `envelope_version_check` string. No network. | ✅ False positive |

### Frontend

| File / Pattern | Finding | Disposition |
|---|---|---|
| `frontend/src/hooks/useAPI.ts` | Uses `fetch` against `VITE_API_BASE_URL` (default `http://localhost:8000/api`). | ✅ Local API only |
| `frontend/src/sections/Hero.tsx` | Inline SVG data-URI background image. | ✅ No network |
| `frontend/index.html` | Loads Google Fonts via `https://fonts.googleapis.com` and `https://fonts.gstatic.com`. | ⚠️ External UI dependency; documented below |

### Scripts

| File / Pattern | Finding | Disposition |
|---|---|---|
| `scripts/generate_graveyard.py` | Static fixture generator; no network. | ✅ No runtime call |

---

## Remaining Surface Area

### Google Fonts (frontend)

The landing page loads fonts from Google. To be fully local-first:

- **Option A:** Vendor the fonts into `frontend/public/fonts/` and update `index.html`.
- **Option B:** Accept the external font load as a build-time UI dependency; user data never flows through it.

**Recommendation:** Option A if packaging an offline installer; Option B is acceptable for the web-hosted dev build.

---

## Gating Policy

The `backend/local/settings.py` `FEATURE_FLAGS` dict is the canonical kill-switch for every cloud feature. Any future cloud feature must:

1. Add its key to `FEATURE_FLAGS` with default `False`.
2. Call `guard_feature(name)` or `guard_cloud_call(name)` before making any outbound request.
3. Document the opt-in env var in `.env.example` and `docs/OFFLINE_BEHAVIOR.md`.

---

## Tests

`backend/tests/test_local_first.py` (or equivalent) should assert that, with `TAXFLOW_RUNTIME_MODE=offline`:

- `guard_cloud_call("plaid")` raises.
- `feature_enabled("stripe")` is `False`.
- `run_self_test(require_no_network=False)` does not raise even if network is present.
- `is_offline()` returns `True` when the env var is set.

These tests are already present or can be added to `test_local_first.py`.

---

## Sign-Off

No code changes were required to satisfy the audit. The existing `FEATURE_FLAGS` and offline runtime mode provide the required gating. The only open item is the Google Fonts dependency, which is a UI/packaging decision rather than a runtime data leak.
