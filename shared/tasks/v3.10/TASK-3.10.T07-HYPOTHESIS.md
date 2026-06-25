# TASK-3.10.T07 — Hypothesis Property Tests

**Owner:** TBD  
**Goal:** Add property-based tests for date parsing, amount formatting, and reconciliation math.

## Files

- `backend/tests/test_hypothesis_date_amount.py`
- `backend/tests/test_hypothesis_reconciliation.py`
- Target functions in `backend/utils/dates.py`, `backend/utils/money.py`

## Requirements

1. Use `hypothesis` with pytest.
2. Cover date parsing across leap years, timezones, malformed strings.
3. Cover amount formatting/rounding with arbitrary decimals.
4. Find at least one real edge case and fix it.

## Tests

- Property tests run in CI without network.
- At least one edge case documented and fixed.

## Report

Edge cases found, files changed, test command + result.
