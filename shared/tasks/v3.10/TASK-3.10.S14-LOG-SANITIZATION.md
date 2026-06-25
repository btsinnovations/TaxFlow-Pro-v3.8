# TASK-3.10.S14 — Log Sanitization

**Owner:** TBD  
**Goal:** Ensure no descriptions, account numbers, or balances leak into plain-text logs.

## Files

- All `print()` and logging call sites
- `backend/utils/logging.py`
- `backend/tests/test_log_sanitization.py`

## Requirements

1. Audit all logging for PII/sensitive data.
2. Redact or truncate sensitive fields in log messages.
3. Add helper for safe logging of transaction objects.

## Tests

- Transaction with sensitive description logged → description redacted.
- Account number logged → masked.
- Balance logged → rounded or masked.

## Report

Files changed, violations found, helper introduced.
