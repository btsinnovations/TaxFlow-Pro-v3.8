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

## Supporting Routers with Missing Tests

These routers are wired but have no dedicated test file in `backend/tests/`:

| Router | What it does | Risk |
|--------|-------------|------|
| `accounts` | Legacy account CRUD | Likely superseded by COA + v3.11 modules |
| `clients` | Client/tenant CRUD | Used by tenant resolution; needs tests |
| `transactions` | Core transaction CRUD + running balance | High — used everywhere |
| `upload` | PDF/CSV statement upload + parsing | High — main import path |
| `dashboard` | Dashboard stats | Medium |
| `audit` | Audit logs / verify | Medium |
| `tax` | Tax summary | Medium |
| `gl` | General ledger entries | Medium |
| `ml` | ML categorization toggle/train | Low for v3.11 (offline) |
| `health` | Health / migrations / config | Low |
| `auth` | Boot, login, refresh, me | Covered indirectly by `test_api.py` and `conftest.py` |
| `depreciation` | Asset depreciation | Has `test_depreciation.py` (audit showed OK) |
| `flags` | Flagged transactions | Has `test_flags.py` (audit showed OK) |

## Action Items

1. **For v3.11:** Do not block on missing tests for legacy/sup routers unless they break the full suite. The 13 module routers + parser + OFX + tax rules are the exit criteria.
2. **For v3.11.5 / hardening:** Add dedicated tests for `transactions`, `upload`, `clients`, `auth`, and `dashboard`.
3. **Verify:** `rules.py` exposes both base `rules_router` and `tax_rules_router`; ensure no route collisions.
