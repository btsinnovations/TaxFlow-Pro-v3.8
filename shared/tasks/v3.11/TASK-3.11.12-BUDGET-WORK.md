# TASK-3.11.12 — Budget & Cash Flow Forecasting

**Owner:** Jane  
**Goal:** Complete budget module: tests, budget-vs-actual logic, cash-flow forecast, and frontend component.

## Current State

- `backend/accounting/budget.py` — set budget line, budget vs actual, cash-flow forecast stub
- `backend/routers/budget.py` — endpoints exist
- Model: `BudgetLine`
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_budget.py` — new
- `frontend/src/components/reports/Budget.tsx` — new

## Backend Tests Required

1. `test_set_budget_line`
   - Set line for GL account + period; assert persisted.
2. `test_budget_vs_actual`
   - Set budget, create transactions in same period mapped to account; assert actual, variance.
3. `test_budget_vs_actual_respects_period`
   - Transactions in different period excluded.
4. `test_cash_flow_forecast_returns_projection`
   - Any return shape is fine; test that 6 months are produced and values are numeric.

## Frontend

- `Budget.tsx`: set budget lines by account/period, view budget vs actual table, see cash-flow forecast chart.

## Constraints

- Period format `YYYY-MM`.
- Offline-only.

## Report

Files changed, test command + result, blockers.
