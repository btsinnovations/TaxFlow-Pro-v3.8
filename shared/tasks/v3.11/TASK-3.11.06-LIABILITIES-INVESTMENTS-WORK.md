# TASK-3.11.06 — Loans, Credit Lines, Investments

**Owner:** Jane  
**Goal:** Complete liabilities and investments modules: tests, edge cases, and any missing API behavior.

## Current State

- `backend/accounting/liabilities.py` — amortization schedule + loan schedule + credit-line stub
- `backend/routers/liabilities.py` — endpoints exist
- `backend/accounting/investments.py` — FIFO lot tracking + holdings
- `backend/routers/investments.py` — endpoints exist
- Models: `LoanSchedule`, `InvestmentLot`
- Tests: **missing** for both modules

## Files

- `backend/tests/test_liabilities.py` — new
- `backend/tests/test_investments.py` — new

## Liability Tests Required

1. `test_amortization_schedule_math` — verify payment, interest, principal, balance for a sample loan.
2. `test_zero_interest_amortization` — equal principal payments when rate = 0.
3. `test_create_loan_schedule_attached_to_account` — create account, call `create_loan_schedule`, assert `LoanSchedule` row.
4. `test_loan_schedule_invalid_account` — non-existent account raises `LiabilityError`.
5. `test_credit_line_available_stub` — account with numeric `account_number_masked` returns parsed limit.

## Investment Tests Required

1. `test_add_lot` — add a lot, assert row in `InvestmentLot`.
2. `test_holdings_grouped_by_symbol` — add multiple lots for same symbol, assert summed shares and cost basis.
3. `test_sell_lots_fifo_partial` — sell fewer shares than first lot; remaining lot still open.
4. `test_sell_lots_fifo_multiple` — sell across multiple lots; realized gain correct.
5. `test_sell_lots_fifo_over_sell` — sell more than owned raises `InvestmentError`.

## Router Tests (optional but recommended)

- `POST /liabilities/loan-schedule` returns 200.
- `POST /liabilities/amortization` returns schedule.
- `POST /investments/lots` creates a lot.
- `POST /investments/{account_id}/sell` returns realized gain rows.
- `GET /investments/{account_id}/holdings` lists grouped holdings.

## Constraints

- Use `Decimal` precision; compare with `quantize`.
- Keep offline-first.

## Report

Files changed, test command + result, blockers.
