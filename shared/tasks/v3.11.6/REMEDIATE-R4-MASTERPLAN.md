# R4 — Tax Forms + Adjusting Entries + Year-End Package Masterplan

## Objective
Implement missing tax forms (1065, 1120-S, 8825, 4562, Schedule E), add adjusting-entry designation, and produce a downloadable year-end package zip.

## Branch
`v3.11.6-dev-REMEDIATE-R4-tax-and-ye` (already pushed to origin)

## Background from Code Research
- `backend/accounting/tax_exports.py` has `schedule_c()` and `form_1099()` only.
- `TaxLineMapping` model maps COA accounts to form lines.
- `backend/routers/tax_exports.py` likely exposes `/tax/export` endpoints.
- `backend/routers/gl.py` allows manual GL entries but has no adjusting-entry flag.
- No year-end package endpoint exists.

## Tasks

### 1. Extend `backend/accounting/tax_exports.py`
- Add form line dictionaries:
  - `FORM_1065_LINES` — ordinary business income, rental real estate, guaranteed payments, deductions, etc.
  - `FORM_1120S_LINES` — ordinary income/loss, deductions, Schedule K-1 placeholders.
  - `FORM_8825_LINES` — rental income/loss by property.
  - `FORM_4562_LINES` — depreciation, Section 179, bonus, ADS.
  - `SCHEDULE_E_LINES` — supplemental rental/royalty income.
- Implement functions:
  - `form_1065(db, tenant_id, user_id, start, end)`
  - `form_1120s(...)`
  - `form_8825(...)`
  - `form_4562(...)` — pull from `DepreciationAsset` and depreciation schedules.
  - `schedule_e(...)`
- Refactor shared logic into `_line_totals_for_form(form_name)` helper.

### 2. Adjusting entries
- Extend `GeneralLedgerEntry.entry_type` enum from R2 with `adjusting`.
- `POST /ledger/adjusting-entry` endpoint:
  - Same payload as `/ledger/entries` plus optional `review_flag_id`.
  - Sets `entry_type='adjusting'`.
  - Enforces `Role.bookkeeper` minimum.
- In reports:
  - Mark adjusting entries in line-item detail.
  - Ensure adjusting entries are not double-counted in regular totals.

### 3. Year-end package zip
- New module `backend/accounting/year_end.py`:
  - `generate_year_end_package(db, tenant_id, user_id, year) -> zip_bytes`
  - Include CSVs/JSON:
    - trial_balance.csv
    - income_statement.csv
    - balance_sheet.csv
    - general_ledger.csv (with `entry_type` column)
    - schedule_c.json
    - form_1065.json
    - form_1120s.json
    - form_8825.json
    - form_4562.json
    - schedule_e.json
    - form_1099_summary.csv
    - review_flags.json
    - workpaper_index.json
- `GET /tax/year-end-package?year=2026` endpoint.

### 4. Tests
- `backend/tests/test_tax_exports_extended.py`:
  - Each form returns expected keys.
  - Line amounts tie to seeded transactions/COA.
- `backend/tests/test_adjusting_entries.py`:
  - Create adjusting entry.
  - Bookkeeper can; viewer cannot.
  - Reports flag adjusting entries separately.
- `backend/tests/test_year_end_package.py`:
  - Download zip.
  - Assert all files present.
  - Validate JSON/CSV content.

## Acceptance Criteria
- [ ] 1065, 1120-S, 8825, 4562, Schedule E forms produce non-empty data.
- [ ] Tax line amounts tie to ledger/depreciation.
- [ ] Adjusting entries are flagged and separately visible.
- [ ] Year-end zip contains 10+ validated files.
- [ ] All new tests pass on SQLite + PostgreSQL.
- [ ] Full backend regression passes.

## Files Likely to Change
- `backend/accounting/tax_exports.py`
- `backend/accounting/year_end.py` (new)
- `backend/routers/tax_exports.py`
- `backend/routers/gl.py`
- `backend/models.py` (entry_type enum)
- `backend/schemas.py`
- `backend/tests/test_tax_exports_extended.py` (new)
- `backend/tests/test_adjusting_entries.py` (new)
- `backend/tests/test_year_end_package.py` (new)

## Dependencies
- Must wait for R2 `GeneralLedgerEntry.entry_type` enum.
- Rebase after R2 merges.
