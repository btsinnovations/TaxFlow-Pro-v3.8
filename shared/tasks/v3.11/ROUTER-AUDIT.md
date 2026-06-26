# Backend Router Audit — 2026-06-25

**Branch:** `v3.11-dev`  
**Routers wired in `backend/api.py`:** 31

## v3.11 Module Routers (all have tests)

| Router | Prefix in `api.py` | Test file | Status |
|--------|-------------------|-----------|--------|
| `coa` | `/api` | `backend/tests/test_coa.py` | ✅ 13 passed |
| `profiles` | `/api` | `backend/tests/test_roles.py` | ✅ |
| `recurring` | `/api` | `backend/tests/test_recurring.py` | ✅ |
| `checks` | `/api` | `backend/tests/test_checks.py` | ✅ |
| `inventory` | `/api` | `backend/tests/test_inventory.py` | ✅ |
| `fx` | `/api` | `backend/tests/test_fx.py` | ✅ |
| `reconciliation` | `/api` | `backend/tests/test_reconciliation.py` | ✅ |
| `reports` | `/api` | `backend/tests/test_reports.py` | ✅ |
| `budget` | `/api` | `backend/tests/test_budget.py` | ✅ |
| `invoicing` | `/api` | `backend/tests/test_invoicing.py` | ✅ |
| `liabilities` | `/api` | `backend/tests/test_liabilities.py` | ✅ |
| `investments` | `/api` | `backend/tests/test_investments.py` | ✅ |
| `tax_exports` | `/api` | `backend/tests/test_tax_exports.py` | ✅ |

## New v3.11 Feature Routers

| Router | Prefix | Test file | Status | Notes |
|--------|--------|-----------|--------|-------|
| `rules.tax_rules_router` | `/api` | `backend/tests/test_tax_rules_search.py` | ✅ 6 passed | Search/filter API |
| `imports` | `/api` | `backend/tests/test_parser_detection.py`, `backend/tests/test_ofx.py` | ✅ 63 + 7 passed | Detect + OFX import |
| `export` | `/api` | `backend/tests/test_export.py` | ✅ | Export endpoints |

## Supporting Routers — Coverage Verified (2026-06-25)

A targeted test run covering all support-router functionality was executed with `-k "accounts or clients or transactions or upload or dashboard or audit or tax or gl or ml or health or auth"`.

**Result:** 161 passed, 482 deselected, 0 failed.

These routers are wired in `backend/api.py` and are exercised by existing tests, even though no single dedicated test file exists for each:

| Router | Coverage source | Risk |
|--------|----------------|------|
| `accounts` | `test_coa.py`, `test_api.py` | Low — superseded by COA + v3.11 modules |
| `clients` | `test_single_user_mode.py`, `test_api.py` | Medium — tenant resolution path exercised |
| `transactions` | `test_register.py`, `test_idempotent_upload.py`, `test_export.py`, `test_api.py` | Medium-high — core CRUD + filters covered indirectly |
| `upload` | `test_api.py`, `test_upload_security.py`, `test_temp_file_cleanup.py`, `test_path_traversal.py`, `test_parser_unification.py` | High — main import path covered |
| `dashboard` | `test_api.py` | Low |
| `audit` | `test_audit_trail.py`, `test_audit_sign.py`, `test_append_only.py` | Medium |
| `tax` | `test_tax_exports.py`, `test_api.py` | Low — same underlying data as tax_exports |
| `gl` | `test_workpaper_ref.py`, `test_api.py` | Low |
| `ml` | `test_api.py`, `test_ml_pipeline.py` | Low for v3.11 (offline) |
| `health` | `test_api.py`, `test_bootstrap.py`, `test_migration_health.py` | Low |
| `auth` | `test_hybrid_auth.py`, `test_api.py` | High — comprehensively covered |
| `depreciation` | `test_depreciation.py` | OK |
| `flags` | `test_flags.py` | OK |

## Action Items

1. **For v3.11:** Backend support-router coverage is confirmed via existing tests (161 passed). No new dedicated test files required for the v3.11.0 tag.
2. **For v3.11.5 / hardening:** Optionally split `transactions`, `upload`, `clients`, and `dashboard` into dedicated router test files for clarity, even though they are already covered indirectly.
3. **Verify:** `rules.py` exposes both base `rules_router` and `tax_rules_router`; ensure no route collisions.
