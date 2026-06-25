# TASK-3.11.08 — Multi-Currency

**Owner:** Jane  
**Goal:** Complete FX module: tests, rate override, conversion logic.

## Current State

- `backend/accounting/fx.py` — `set_rate` and `convert` helpers
- `backend/routers/fx.py` — endpoints exist
- Model: `FXRate`
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_fx.py` — new
- `frontend/src/components/fx/FXRates.tsx` — new

## Backend Tests Required

1. `test_set_rate`
   - Set USD → CAD rate 1.35; assert row persisted.
2. `test_convert_uses_latest_rate`
   - Set rate, convert amount, assert expected result.
3. `test_convert_inverse_rate`
   - Only USD→CAD stored; converting CAD→USD uses inverse.
4. `test_convert_missing_rate_fails`
   - No rate for currency pair raises `FXError`.
5. `test_convert_uses_closest_prior_rate`
   - Multiple rates on different dates; conversion picks latest on or before `as_of`.

## Frontend

- `FXRates.tsx`: table of stored rates, form to add rate, quick converter widget.

## Constraints

- No live FX API; all rates manual.
- `Decimal` precision.

## Report

Files changed, test command + result, blockers.
