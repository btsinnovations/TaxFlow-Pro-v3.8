# R2 — Period Close Automation Masterplan

## Objective
Implement month/year-end period close: zero income/expense accounts, post net income to Retained Earnings, and lock the period from further changes.

## Branch
`v3.11.6-dev-REMEDIATE-R2-period-close` (already pushed to origin)

## Background from Code Research
- `backend/models.py` has a `Period` model but no `is_closed` / `closed_at` / `closed_by` fields.
- COA seed includes `Retained Earnings` (3100) and standard income/expense accounts.
- `backend/routers/gl.py` allows manual GL entries.
- Reports derive period data from transactions; once R1 GL bridge lands, close should use GL entries.

## Tasks

### 1. Schema changes
- Alembic migration to add to `Period`:
  - `is_closed` boolean default False
  - `closed_at` DateTime nullable
  - `closed_by_profile_id` Integer FK nullable
- Migration to add `entry_type` enum to `GeneralLedgerEntry`:
  - `regular`, `adjusting`, `closing`, `system`
  - Default `regular`
- Migration must be dialect-aware.

### 2. Create `backend/accounting/period_close.py`
- `close_period(db, tenant_id, user_id, period_id, profile_id)`:
  - Load period; fail if already closed.
  - Find earliest open prior period; enforce sequential close (no gaps).
  - Compute income total and expense total from GL entries for period.
  - Net income = income - expenses.
  - Create closing GL entries:
    - Debit each income account by its balance (zeroing).
    - Credit each expense account by its balance (zeroing).
    - Credit (or debit) Retained Earnings by net income.
  - All entries `entry_type='closing'`, `source_id='period_close:{period_id}'`.
  - Mark period closed.
  - Audit log entry.
- `reopen_period(db, tenant_id, user_id, period_id, profile_id)`:
  - Owner/admin only.
  - Reverse all closing entries for period (delete or post reversals).
  - Mark period open.
  - Audit log entry.
- `get_period_status(db, tenant_id, user_id, period_id) -> dict`.

### 3. Router endpoints in `backend/routers/periods.py` (new) or extend existing periods router
- `POST /periods/{id}/close`
- `POST /periods/{id}/reopen`
- `GET /periods/{id}/status`
- Enforce `Role.bookkeeper` minimum for close; `Role.owner` for reopen.

### 4. Hard guards across app
- Add helper `is_period_closed(db, tenant_id, period_id)`.
- Reject in routers:
  - `POST /transactions` if date falls in closed period.
  - `POST /imports/ofx`, `POST /upload` if statement period overlaps closed period.
  - `POST /ledger/entries` if date in closed period (except `entry_type='closing'` by reopen flow).
  - `POST /reconciliation/{id}/complete` if statement date in closed period.
- Reject edits/deletes of GL entries with `entry_type='closing'`.

### 5. Tests
- `backend/tests/test_period_close.py`:
  - Close Q1 with income 50K, expenses 30K → Retained Earnings +20K.
  - Reopen → balances restored, closing entries gone.
  - Closed period rejects new transaction with 422.
  - Closing out-of-sequence period fails.
- Extend `test_reports.py` to ensure closing entries don't corrupt P&L.

## Acceptance Criteria
- [ ] Period close zeros all income/expense accounts and posts net to Retained Earnings.
- [ ] Reopening restores original balances.
- [ ] All writes to closed period return 422.
- [ ] Closing entries cannot be edited/deleted directly.
- [ ] `pytest backend/tests/test_period_close.py` passes on SQLite + PostgreSQL.
- [ ] Full backend regression passes on both backends.

## Files Likely to Change
- `backend/models.py`
- `alembic/versions/<new>_v3_11_6_r2_period_close.py`
- `backend/accounting/period_close.py` (new)
- `backend/routers/periods.py` (new or extend existing)
- `backend/routers/transactions.py`
- `backend/routers/imports.py`
- `backend/routers/upload.py`
- `backend/routers/gl.py`
- `backend/routers/reconciliation.py`
- `backend/schemas.py`
- `backend/tests/test_period_close.py` (new)

## Dependencies
- Must wait for R1 `GeneralLedgerEntry.entry_type` enum.
- After R1 merges, rebase this branch.
