# TASK-3.11.13 — Invoicing / A/P / A/R

**Owner:** Jane  
**Goal:** Complete lightweight invoicing module: tests, aging report, payment tracking, frontend component.

## Current State

- `backend/accounting/invoicing.py` — create invoice/bill, record payment, list, aging report
- `backend/routers/invoicing.py` — endpoints exist
- Models: `Invoice`, `InvoiceLineItem`, `Payment`
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_invoicing.py` — new
- `frontend/src/components/accounts/Invoicing.tsx` — new

## Backend Tests Required

1. `test_create_invoice`
   - Create invoice with line items; assert total computed correctly.
2. `test_create_bill`
   - Create bill (`is_bill=True`); assert total and status.
3. `test_record_payment`
   - Record partial payment; assert `amount_paid`, status remains "open".
4. `test_record_payment_full`
   - Pay full amount; status becomes "paid".
5. `test_over_payment_fails`
   - Payment > total raises `InvoicingError`.
6. `test_aging_report_buckets`
   - Create invoices with due dates in past/current/future; assert aging buckets.

## Frontend

- `Invoicing.tsx`: tabs for Invoices/Bills, list view, create form, record payment modal, aging report.

## Constraints

- Offline-only.
- Use `Decimal` precision.

## Report

Files changed, test command + result, blockers.
