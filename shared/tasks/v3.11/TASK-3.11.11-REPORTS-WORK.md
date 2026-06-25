# TASK-3.11.11 — Reports Center

**Owner:** Jane  
**Goal:** Complete reports module: tests, P&L and trial balance accuracy, frontend component.

## Current State

- `backend/accounting/reports.py` — profit_and_loss, trial_balance
- `backend/routers/reports.py` — endpoints exist
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_reports.py` — new
- `frontend/src/components/reports/Reports.tsx` — new

## Backend Tests Required

1. `test_profit_and_loss_zeros`
   - No transactions → income 0, expenses 0, net 0.
2. `test_profit_and_loss_income_and_expense`
   - Map GL accounts to income/expense; create transactions; assert net = income - expenses.
3. `test_trial_balance_debits_equal_credits`
   - Create journal entries; trial balance rows sum to zero difference.
4. `test_reports_respect_date_range`
   - Transactions outside range excluded from P&L.

## Frontend

- `Reports.tsx`: select report type, date range, run report, display results table.
- Export to CSV/JSON/PDF deferred if non-trivial.

## Constraints

- Use existing `GLAccount` account_type classification.
- Offline-only.

## Report

Files changed, test command + result, blockers.
