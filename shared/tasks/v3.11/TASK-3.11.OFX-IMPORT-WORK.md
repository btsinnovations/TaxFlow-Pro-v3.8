# TASK-3.11.OFX — OFX / Live Feed Integration

**Owner:** Jane  
**Goal:** Implement OFX/QFX file import and transaction deduplication; scaffold local live feed if feasible.

## Current State

- No OFX parser module yet.
- `backend/models.py` may need `fitid` column for unique transaction IDs.
- `backend/routers/imports.py` or similar handles CSV/statement imports.
- Tests: **missing**

## Files

- `backend/parsers/ofx.py` — new OFX/QFX parser.
- `backend/routers/imports.py` — add `POST /api/imports/ofx`.
- `backend/tests/test_ofx_parser.py` — new
- `backend/tests/test_ofx_endpoint.py` — new
- `backend/tests/test_ofx_dedup.py` — new
- `frontend/src/components/upload/OFXUpload.tsx` — new
- Alembic migration adding `fitid` to `Transaction`.

## Backend Tests Required

1. `test_ofx_parser_extracts_transactions`
   - Parse a sample OFX file; assert transactions, dates, amounts, FITID.
2. `test_ofx_parser_handles_multiple_accounts`
   - File with multiple <BANKACCTFROM> sections; assert account mapping.
3. `test_ofx_endpoint_imports_transactions`
   - Upload OFX bytes to endpoint; assert `Statement` + `Transaction` rows created.
4. `test_fitid_dedup_skips_duplicates`
   - Import same OFX twice; second import skips duplicate FITIDs.
5. `test_ofx_account_mapping`
   - Import maps to existing account by account number or creates placeholder.

## Live Feed (3.11.OFX.04)

- Scaffold a local OFX directory poller (optional).
- Poll `~/.taxflow/feeds/*.ofx` and import automatically.
- Spike only; disable by default.

## Frontend

- `OFXUpload.tsx`: drag-and-drop OFX file upload, account mapping step, import preview, duplicate summary.

## Constraints

- No cloud bank aggregation APIs (Plaid, Yodlee).
- Offline-first.

## Report

Files changed, test command + result, blockers.
