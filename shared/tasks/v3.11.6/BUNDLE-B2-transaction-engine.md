# Bundle B2 — Core Transaction Engine

**Goal:** Build the unified register, transaction splits, recurring rules, and check register so users can manage money movement in one place.

---

## 3.11.6.B2.01 — Unified Register Backend

### Files
- `backend/accounting/register.py`
- `backend/routers/transactions.py`
- `backend/tests/test_register.py`

### Requirements
- Register view = filterable, sortable list of transactions for the active profile.
- Filters: date range, account, amount range, description search, tags, reconciled status.
- Sort by date, amount, description, account.
- Pagination (offset/limit) + cursor option for large datasets.
- Inline status: cleared, reconciled, pending.
- Bulk operations: delete, tag, change status (authorized roles only).

### Tests
- List transactions with filters.
- Sort ascending/descending.
- Pagination boundary.
- Bulk delete restricted to owner/admin.
- Tenant isolation.

---

## 3.11.6.B2.02 — Transaction Splits Backend

### Files
- `backend/accounting/splits.py`
- `backend/routers/transactions.py` (split endpoints)
- `backend/tests/test_splits.py`

### Requirements
- A transaction can split into multiple line items with independent accounts and amounts.
- Splits stored as JSON in `transactions.splits`.
- Sum of split amounts must equal transaction total (within rounding tolerance).
- Support pre/post allocations (e.g., ATM cash back splits).
- Validation: no empty accounts, no zero amounts, no duplicate splits.

### Tests
- Create split transaction.
- Reject unbalanced splits.
- Edit splits.
- Delete transaction with splits.
- Pre-existing single-line transactions migrate to one-entry splits.

---

## 3.11.6.B2.03 — Recurring / Scheduled Transactions Backend

### Files
- `backend/accounting/recurring.py`
- `backend/routers/recurring.py`
- `backend/tests/test_recurring.py`

### Requirements
- `recurring_rules` table: account_id, description, amount, frequency, start_date, end_date/count, splits JSON, next_run_date, enabled.
- Frequencies: daily, weekly, biweekly, monthly, quarterly, yearly.
- Endpoint to generate pending occurrences up to a target date.
- Endpoint to materialize an occurrence into a real transaction.
- Safe offline execution: generation is idempotent and audited.

### Tests
- Create weekly rule.
- Generate next 4 occurrences.
- Materialize occurrence.
- Disable rule stops generation.
- End-date boundary respected.
- Tenant isolation.

---

## 3.11.6.B2.04 — Check Register Backend

### Files
- `backend/accounting/checks.py`
- `backend/routers/checks.py`
- `backend/tests/test_checks.py`

### Requirements
- Track physical checks issued: check number, payee, amount, date, account, memo.
- Prevent duplicate check numbers per account.
- Mark check as cleared/reconciled.
- Search by check number range.
- Link a check to a transaction (optional).

### Tests
- Record check.
- Duplicate check number rejected.
- Clear check.
- Search by number range.
- Tenant isolation.
