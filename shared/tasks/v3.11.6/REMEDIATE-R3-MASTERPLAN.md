# R3 — Reconciliation Locking Masterplan

## Objective
Prevent modifications to completed reconciliations and their cleared transactions. Provide a reopen path for corrections.

## Branch
`v3.11.6-dev-REMEDIATE-R3-reconciliation-lock` (already pushed to origin)

## Background from Code Research
- `backend/accounting/reconciliation.py` handles import, auto-match, manual match, unmatch, status.
- `backend/routers/reconciliation.py` exposes these as API endpoints with role checks (`bookkeeper` for import).
- `ReconciliationImport` model currently has no `is_completed` / `completed_at` / `completed_by` fields.
- `ReconciliationMatch` links `import_id`, `ledger_tx_id`, `statement_tx_id`.

## Tasks

### 1. Schema changes
- Alembic migration to add to `ReconciliationImport`:
  - `is_completed` boolean default False
  - `completed_at` DateTime nullable
  - `completed_by_profile_id` Integer FK nullable
  - Optional JSON/text `cleared_snapshot` to store matched IDs at completion time.

### 2. Business logic in `backend/accounting/reconciliation.py`
- `complete_reconciliation(db, import_id, user_id, profile_id)`:
  - Verify import exists and belongs to user/tenant.
  - Compute final difference; allow completion only if difference == 0 (configurable).
  - Set `is_completed=True`, `completed_at=now()`, `completed_by_profile_id`.
  - Snapshot cleared transaction IDs.
  - Audit log.
- `reopen_reconciliation(db, import_id, user_id, profile_id)`:
  - Owner/admin only.
  - Set `is_completed=False`.
  - Clear snapshot.
  - Audit log.
- `is_reconciliation_completed(db, import_id) -> bool`.

### 3. Guards
- In `manual_match`, `unmatch`, and all update/delete helpers: raise `ReconciliationError` if `is_completed`.
- In `transactions.py` update/delete/void: check if transaction is cleared by any completed reconciliation. If so, return 409 with reconciliation ID.

### 4. Router endpoints
- `POST /reconciliation/{import_id}/complete`
- `POST /reconciliation/{import_id}/reopen`
- Enforce `Role.bookkeeper` for complete, `Role.owner` for reopen.

### 5. Tests
- `backend/tests/test_reconciliation_lock.py`:
  - Complete reconciliation with difference=0.
  - After complete, `auto-match`, `manual-match`, `unmatch` return 409.
  - After complete, editing a cleared transaction returns 409.
  - Reopen allows match/unmatch and transaction edits.
  - Attempting to complete with non-zero difference returns 400 (configurable).

## Acceptance Criteria
- [ ] Completed reconciliation rejects match/unmatch operations.
- [ ] Cleared transactions in completed reconciliation reject edits/deletes.
- [ ] Reopen restores mutability (owner/admin only).
- [ ] Audit entries recorded for complete/reopen.
- [ ] `pytest backend/tests/test_reconciliation_lock.py` passes on SQLite + PostgreSQL.
- [ ] Full backend regression passes on both backends.

## Files Likely to Change
- `backend/models.py`
- `alembic/versions/<new>_v3_11_6_r3_reconciliation_lock.py`
- `backend/accounting/reconciliation.py`
- `backend/routers/reconciliation.py`
- `backend/routers/transactions.py` (cleared-txn guard)
- `backend/schemas.py`
- `backend/tests/test_reconciliation_lock.py` (new)

## Dependencies
- None. Can run in parallel with R1/R2.
