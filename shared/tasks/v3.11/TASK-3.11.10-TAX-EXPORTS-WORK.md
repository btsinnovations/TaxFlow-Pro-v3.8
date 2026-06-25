# TASK-3.11.10 — Tax Filing Exports

**Owner:** Jane  
**Goal:** Complete tax export module: tests, Schedule C logic, tax-line mappings, and frontend component.

## Current State

- `backend/accounting/tax_exports.py` — Schedule C export + mapping helpers
- `backend/routers/tax_exports.py` — endpoints exist
- Model: `TaxLineMapping`
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_tax_exports.py` — new
- `frontend/src/components/tax/TaxExports.tsx` — new

## Backend Tests Required

1. `test_set_mapping`
   - Create GL account, map to Schedule C line; assert `TaxLineMapping` row.
2. `test_list_mappings`
   - Multiple mappings; list returns only current tenant/user mappings.
3. `test_schedule_c_empty`
   - No transactions in range → all lines zero.
4. `test_schedule_c_sums_by_line`
   - Create transactions categorized/mapped to line "Advertising" and "Office Expense"; assert totals.
5. `test_schedule_c_respects_date_range`
   - Transactions outside range excluded.

## Frontend

- `TaxExports.tsx`: date range picker, mapping editor (COA account → form/line), Schedule C preview table, export button (CSV/JSON).

## Constraints

- Start with Schedule C only; other forms can be added later.
- Offline-only.

## Report

Files changed, test command + result, blockers.
