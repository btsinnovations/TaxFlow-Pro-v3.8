# R5 — Phase C Business Operations Gaps Masterplan

## Objective
Implement sales tax liability tracking, mileage log, and vendor-keyed 1099 tracking.

## Branch
`v3.11.6-dev-REMEDIATE-R5-phase-c-ops` (already pushed to origin)

## Background from Code Research
- `backend/accounting/invoicing.py` has Invoice/Bill CRUD, payments, aging.
- `backend/routers/invoicing.py` exposes endpoints with role checks.
- 1099 currently uses transaction description as payee (`backend/accounting/tax_exports.py`).
- No sales tax or mileage models exist.

## Tasks

### 1. Sales Tax Liability
- Add models:
  - `SalesTaxRate` (tenant_id, name, jurisdiction, rate decimal, effective_date, is_active)
  - `SalesTaxPayment` (tenant_id, date, amount, sales_tax_rate_id, memo)
- CRUD endpoints under `/api/sales-tax/rates` and `/api/sales-tax/payments`.
- Auto-split on invoice create:
  - If line item has `tax_rate_id`, compute tax amount.
  - Invoice total = net + tax.
  - When invoice is posted/created, call GL bridge (R1) to generate:
    - Debit A/R (asset)
    - Credit Revenue (income) for net amount
    - Credit Sales Tax Payable (liability) for tax amount
  - Ensure `sales_tax_liability` aging report can show unpaid tax by jurisdiction.
- Tests:
  - Invoice with 7% tax → GL entries balance and Sales Tax Payable credited.
  - Payment of sales tax reduces liability.

### 2. Mileage Log
- Add model:
  - `MileageLog` (tenant_id, user_id, date, purpose, miles, vehicle, rate_cents, is_business)
- Default IRS rate table: 2026 = $0.67/mile (override allowed).
- Endpoints:
  - `POST /mileage/log`
  - `GET /mileage/log`
  - `GET /mileage/deduction?year=2026`
- Tests:
  - 1,000 business miles at $0.67 = $670 deduction.
  - Personal miles excluded.

### 3. Vendor-Keyed 1099
- Add model:
  - `Vendor` (tenant_id, name, tin, address, type, threshold_override, is_active)
- Add `vendor_id` to `Invoice`/`Payment`/`Transaction` where applicable.
- Migration to add columns and create vendors from existing transaction descriptions (optional heuristic).
- Update `form_1099()` to group by vendor record instead of description.
- Endpoints under `/api/vendors`.
- Tests:
  - Pay vendor $700 → flagged in 1099 summary.
  - Pay vendor $500 → not flagged.

## Acceptance Criteria
- [ ] Sales tax auto-split creates correct GL entries and liability report.
- [ ] Mileage log computes deduction at IRS rate.
- [ ] 1099 summary groups by vendor and respects $600 threshold.
- [ ] All new tests pass on SQLite + PostgreSQL.
- [ ] Full backend regression passes.

## Files Likely to Change
- `backend/models.py`
- `alembic/versions/<new>_v3_11_6_r5_phase_c_ops.py`
- `backend/accounting/invoicing.py`
- `backend/accounting/tax_exports.py`
- `backend/routers/invoicing.py`
- `backend/routers/sales_tax.py` (new)
- `backend/routers/mileage.py` (new)
- `backend/routers/vendors.py` (new)
- `backend/schemas.py`
- `backend/tests/test_sales_tax.py` (new)
- `backend/tests/test_mileage.py` (new)
- `backend/tests/test_vendor_1099.py` (new)

## Dependencies
- Must wait for R1 GL bridge (sales tax auto-posting).
- Rebase after R1 merges.
