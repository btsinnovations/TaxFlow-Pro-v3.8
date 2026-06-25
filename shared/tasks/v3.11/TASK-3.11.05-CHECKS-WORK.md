# TASK-3.11.05 — Check Register

**Owner:** Jane  
**Goal:** Complete the check register module: tests, edge cases, and frontend component.

## Current State

- `backend/accounting/checks.py` — domain logic exists (issue, list, void)
- `backend/routers/checks.py` — API endpoints exist
- `backend/models.py` — no dedicated Check model; checks stored as `Transaction` rows with `tx_type="check"` and synthetic `Statement(filename="__checks__")`
- Frontend component not created yet
- Tests: **missing**

## Files to Modify / Create

- `backend/tests/test_checks.py` — new
- `frontend/src/components/register/CheckRegister.tsx` — new (or extend Register)

## Backend Tests Required

1. `test_issue_check_creates_transaction`
   - Create an `Account` and call `issue_check`.
   - Assert transaction created, `tx_type="check"`, description contains check number.
   - Assert synthetic `Statement` with `filename="__checks__"` created.
2. `test_check_number_increments`
   - Issue two checks on same account; second check number > first.
3. `test_list_checks_filters_by_type`
   - Add a debit transaction and a check; `list_checks` returns only check.
4. `test_void_check`
   - Issue check, then void; assert `tx_type="void"` and description contains "VOIDED".
5. `test_void_already_voided_fails`
   - Void twice; second call raises `CheckError`.
6. `test_issue_check_invalid_account`
   - Non-existent account raises `CheckError` (router returns 404).

## Router Tests Required

- `POST /checks/` returns 201 with check details.
- `GET /checks/{account_id}` lists checks.
- `PATCH /checks/{transaction_id}/void` voids a check.

## Frontend

- Build `CheckRegister.tsx` or extend existing `Register.tsx` with a "Checks" filter.
- Columns: date, check number, payee, amount, status, void action.
- "Issue Check" button opens form: payee, amount, date, memo.

## Constraints

- Do not break existing transaction/register tests.
- Keep offline-first; no external calls.
- All money amounts use `Decimal` in domain, float in API responses.

## Report

When complete, report files changed, focused test command + result, and any blockers.
