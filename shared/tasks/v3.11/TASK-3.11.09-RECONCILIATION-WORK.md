# TASK-3.11.09 — Bank Reconciliation

**Owner:** Jane  
**Goal:** Complete reconciliation module: tests, OFX/QFX statement-row ingestion, and frontend component.

## Current State

- `backend/accounting/reconciliation.py` — import statement, auto-match (placeholder), status
- `backend/routers/reconciliation.py` — endpoints exist
- Models: `ReconciliationImport`, `ReconciliationMatch`
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_reconciliation.py` — new
- `frontend/src/components/reconciliation/Reconciliation.tsx` — new

## Backend Tests Required

1. `test_import_statement`
   - Create account, import statement balance; assert `ReconciliationImport` row.
2. `test_reconciliation_status_no_matches`
   - Imported statement balance $1,000; no matches → cleared 0, outstanding sum of ledger, difference $1,000.
3. `test_auto_match_by_amount_and_date`
   - Create ledger transaction, import statement with matching amount and date within window; assert `ReconciliationMatch` created.
4. `test_auto_match_no_match_outside_window`
   - Date outside window → no match.
5. `test_reconciliation_status_after_match`
   - After auto-match, cleared equals matched amount, difference reduced.

## Needed Enhancement

- `auto_match` currently iterates over an empty list (`for stmt_row in []`).
- Refactor to accept a list of statement rows from the caller (OFX/CSV parser).
- Endpoint should support optional `statement_rows` JSON payload for tests and manual imports.

## Frontend

- `Reconciliation.tsx`: select account, enter statement balance/date, upload/list statement rows, run auto-match, show cleared/outstanding/difference.

## Constraints

- Offline-first; statement rows may come from OFX file or manual entry.

## Report

Files changed, test command + result, blockers.
