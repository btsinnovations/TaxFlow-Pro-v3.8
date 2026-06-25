# TASK-3.10.S12 — Import Format Sanitization

**Owner:** TBD  
**Goal:** Sanitize OFX, QIF, and CSV imports before processing.

## Files

- `backend/parsers/ofx_parser.py`
- `backend/parsers/qif_parser.py`
- `backend/parsers/csv_parser.py`
- `backend/tests/test_import_sanitization.py`

## Requirements

1. CSV: reject formula-injection prefixes (`=`, `+`, `-`, `@`).
2. OFX/QIF: reject oversized or malformed records.
3. Route all import formats through parser subprocess sandbox.

## Tests

- CSV formula cell sanitized or rejected.
- Malformed OFX/QIF rejected cleanly.
- Valid imports still work.

## Report

Files changed, sanitization rules, test results.
