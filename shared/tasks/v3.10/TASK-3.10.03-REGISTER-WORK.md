# TASK-3.10.03 — Unified Register + Transactions

**Owner:** Jane (when assigned)
**Goal:** Build a unified, register-style transaction view with inline editing, manual entry, splits, and bulk actions.

## Files

- `backend/accounting/register.py` — register query helpers
- `backend/routers/transactions.py` — existing router extended
- `backend/schemas.py` — transaction + split schemas
- `frontend/src/components/register/Register.tsx` — TanStack Table register
- `frontend/src/components/register/SplitEditor.tsx` — split transaction editor
- `backend/tests/test_register.py`
- `backend/tests/test_splits.py`

## Requirements

1. Register shows transactions for a selected account with running balance.
2. Inline editing for date, payee, memo, amount, category.
3. Manual transaction entry via inline empty row or modal.
4. Bulk edit/delete via row selection.
5. Split transactions:
   - Split by category, account, and tax line item.
   - Allocation must sum to total.
6. Keyboard navigation is mouse-first; keyboard shortcuts optional.

## Tests

- List register for account.
- Inline update transaction.
- Bulk delete selected rows.
- Create split transaction.
- Split allocation validation.
- Running balance correctness.

## Constraints

- All existing transaction tests must still pass.
- Frontend uses shadcn/ui + TanStack Table.
- Offline-only.
