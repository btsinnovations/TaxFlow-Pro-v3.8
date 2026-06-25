# TASK-3.10.01 — Chart of Accounts (COA)

**Owner:** Jane (when assigned)  
**Goal:** Implement a full QB/Xero-style chart of accounts with sub-accounts and migrate existing `accounts`/`gl_accounts` data into it.

## Files to create/modify

- `backend/accounting/coa.py` — core COA logic
- `backend/routers/coa.py` — API endpoints
- `backend/schemas.py` — COA Pydantic schemas
- `backend/models.py` — add `coa_accounts` table (or replace legacy tables)
- `alembic/versions/xxxx_add_coa_accounts_table.py` — migration
- `backend/tests/test_coa.py`
- `frontend/src/components/accounts/COATree.tsx` — tree view (FE can be deferred to FE task)

## Requirements

1. Account fields:
   - `id`, `number` (manual), `name`, `type` (Asset, Liability, Equity, Revenue, Expense), `parent_id` (nullable), `is_active`, `created_at`, `updated_at`
2. Sub-accounts from day one.
3. Prevent circular parent references.
4. Migrate existing `accounts` and `gl_accounts` rows into `coa_accounts` during migration.
5. Update `transactions` table to reference `coa_account_id` where appropriate.
6. Endpoints:
   - `GET /api/coa` — list accounts as tree
   - `POST /api/coa` — create account
   - `PUT /api/coa/{id}` — update account
   - `DELETE /api/coa/{id}` — soft delete (set is_active=false if no transactions)

## Tests (must pass)

- Create root account.
- Create sub-account under root.
- Prevent circular parent (child cannot be its own ancestor).
- Migration preserves legacy balances.
- Soft delete inactive account fails if transactions exist.

## Constraints

- Offline-first; no external calls.
- All new code must have tests.
- Do not break existing transaction endpoints.

## Report

When complete, report files changed, focused test command + result, and any blockers.
