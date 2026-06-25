# TASK-3.10.04 — Recurring / Scheduled Transactions

**Owner:** Jane (when assigned)
**Goal:** Store recurrence rules and generate transaction instances when the app opens.

## Files

- `backend/accounting/recurring.py` — rule engine + instance generation
- `backend/models.py` — add `recurring_rules` table
- `backend/local/scheduler.py` — app-open scheduler
- `backend/routers/recurring.py` — CRUD endpoints
- `backend/tests/test_recurring.py`
- `frontend/src/components/recurring/RecurringRules.tsx` — rules UI

## Requirements

1. Rule fields: account_id, amount, description, frequency, start_date, end_date, count, splits JSON.
2. Frequencies: daily, weekly, bi-weekly, monthly, quarterly, yearly, custom N days.
3. Generate instances only when app opens.
4. No duplicate generation on repeated opens (track last_generated_at or use idempotent creation).
5. Soft-delete rules.

## Tests

- Generate instances for each frequency.
- Respect end_date and count limit.
- No duplicates on second run.
- Update rule and regenerate from rule change date.

## Constraints

- Offline-only.
- All new code tested.
