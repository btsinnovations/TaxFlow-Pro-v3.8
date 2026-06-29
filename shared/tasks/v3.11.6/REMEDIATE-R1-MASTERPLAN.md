# R1 — Double-Entry GL Auto-Posting Masterplan

## Objective
Make every transaction import path (OFX/QFX, PDF/CSV upload, manual create, recurring materialization) automatically generate balanced `GeneralLedgerEntry` debit/credit pairs. Close the #1 critical audit gap.

## Branch
`v3.11.6-dev-REMEDIATE-R1-gl-autopost` (already pushed to origin)

## Background from Code Research
- `backend/routers/gl.py` has `POST /ledger/entries` for manual GL entries.
- `backend/routers/imports.py` `POST /imports/ofx` creates `Statement` + `Transaction` records but no GL entries.
- `backend/routers/transactions.py` `POST /transactions` creates `Transaction` records but no GL entries.
- `backend/routers/recurring.py` materializes rules to `Transaction` records.
- `backend/routers/upload.py` parses PDF/CSV to transactions.
- `backend/accounting/coa.py` already seeds `Retained Earnings` (3100), `Operating Checking` (1020), `Sales Revenue` (4010), etc.
- COA model: `CoaAccount` (hierarchical, integer numbers). Legacy `GLAccount` still used by GL entries.
- Reports (`accounting/reports.py`) currently derive P&L/balance sheet from `Transaction` rows, not GL entries. After GL auto-posting, reports should optionally use GL entries for true double-entry truth.

## Tasks

### 1. Create `backend/accounting/gl_bridge.py`
- `class GLBridge`:
  - `__init__(db, tenant_id, user_id)`
  - `post_for_transaction(txn: models.Transaction) -> list[GeneralLedgerEntry]`
    - Determine cash/bank account = `txn.account_id` mapped to a `GLAccount` or `CoaAccount`.
    - Determine offset account by priority:
      1. `txn.coa_account_id` if set.
      2. `CategorizationRule` match by description + amount.
      3. ML categorizer (mock in tests; real in production).
      4. Default `Uncategorized Income` (4015) or `Uncategorized Expense` (5015).
    - For deposits/income: debit cash, credit income/offset.
    - For withdrawals/expenses: credit cash, debit expense/offset.
    - For transfers: create paired transfer entries (debit target cash, credit source cash) if both accounts known.
    - Return two `GeneralLedgerEntry` objects (not committed).
  - `post_batch(txns: list[Transaction]) -> list[GeneralLedgerEntry]`
  - `ensure_offset_accounts_exist()` — create fallback COA accounts if missing.
  - `is_already_posted(txn) -> bool` — check by `source_id == f"txn:{txn.id}"`.

### 2. Add migration for `GeneralLedgerEntry` enhancements
- Add columns:
  - `entry_type` enum (`regular`, `adjusting`, `closing`, `system`) default `regular`.
  - `source_id` varchar nullable — `txn:{id}`, `import:{id}`, `recurring:{id}`.
  - `import_source` varchar nullable — copy from `Transaction.import_source`.
  - `txn_uid` varchar nullable — for idempotency.
- Make migration dialect-aware (PG vs SQLite) like existing RLS migrations.

### 3. Wire bridge into import paths
- `backend/routers/imports.py` `POST /imports/ofx`:
  - After persisting transactions, call `GLBridge.post_batch()` and commit.
  - Skip any transaction where `is_already_posted` is true.
- `backend/routers/upload.py`:
  - Same pattern for PDF/CSV parser results.
- `backend/routers/transactions.py` `POST /transactions`:
  - After create, post GL entries.
- `backend/routers/recurring.py` `POST /recurring/{id}/materialize`:
  - After generating transactions, post GL entries.

### 4. Add retroactive endpoint
- `POST /ledger/auto-post-batch` (owner/admin only):
  - Query all transactions in tenant without GL entries.
  - Call `GLBridge.post_batch()` and commit.
  - Return count posted.

### 5. Tests
- `backend/tests/test_gl_bridge.py`:
  - Deposit posts debit cash / credit income.
  - Withdrawal posts credit cash / debit expense.
  - Transfer posts debit target / credit source.
  - Missing COA account falls back to Uncategorized.
  - Idempotency: second call posts nothing.
- Extend `test_ofx.py` to assert GL balance after OFX import.
- Extend `test_upload.py` to assert GL balance after PDF/CSV upload.
- Extend `test_recurring.py` to assert GL entries after materialize.
- `test_gl_bridge_integration.py`: import OFX → run trial balance → assert debits=credits.

### 6. Report updates (optional but recommended)
- Add report mode `use_gl_entries=True` to `profit_and_loss`, `trial_balance`, `balance_sheet`.
- Keep existing transaction-based mode as fallback for backward compatibility.

## Acceptance Criteria
- [ ] Importing a 10-row OFX statement creates 20 GL rows (10 debit, 10 credit).
- [ ] Trial balance balances after any import.
- [ ] Re-importing same OFX is idempotent.
- [ ] Manual transaction create produces balanced GL entries.
- [ ] Recurring materialize produces balanced GL entries.
- [ ] `pytest backend/tests/test_gl_bridge*.py` passes on SQLite + PostgreSQL.
- [ ] Full backend regression passes on SQLite + PostgreSQL.

## Files Likely to Change
- `backend/accounting/gl_bridge.py` (new)
- `backend/models.py` (GeneralLedgerEntry columns)
- `alembic/versions/<new>_v3_11_6_r1_gl_entry_enhancements.py` (new)
- `backend/routers/gl.py` (add auto-post endpoint)
- `backend/routers/imports.py`
- `backend/routers/upload.py`
- `backend/routers/transactions.py`
- `backend/routers/recurring.py`
- `backend/accounting/reports.py` (optional GL mode)
- `backend/schemas.py` (GeneralLedgerEntryOut update)
- `backend/tests/test_gl_bridge.py` (new)
- `backend/tests/test_gl_bridge_integration.py` (new)

## Dependencies
- None before starting.
- Blocks R2 (period close needs GL data).
- Blocks R5 invoice tax splits (needs GL bridge for auto-post).
