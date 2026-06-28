# TaxFlow Pro v3.11.6 — Track 7 Masterplan (B5 Invoicing / A/P / A/R)

**Branch:** `v3.11.6-dev-PHASE3-TRACK7-invoicing-ap-ar`  
**Cut from:** `v3.11.6-dev` (after Track 5 merge)  
**Goal:** Deliver lightweight invoicing, accounts payable, and accounts receivable backend.

---

## Why Track 7 Exists

Small-business bookkeeping requires billing customers and tracking bills from vendors. Track 7 adds the A/R and A/P layer without turning TaxFlow into a full accounting suite. It is intentionally lightweight: invoices, bills, line items, payments, and aging.

This track can run **in parallel with Track 6 (B4)** because it depends only on the B1 foundation (COA, users, clients, accounts) and the B2 register/transaction model, not on reconciliation, reports, or tax exports.

---

## Modules & Acceptance Criteria

### B5.01 — Invoicing / A/P / A/R Backend

**Current state:** skeleton exists (`backend/accounting/invoicing.py`, `backend/routers/invoicing.py`, `backend/tests/test_invoicing.py`); supports invoice CRUD, payments, and aging. Bills are modeled via `is_bill=true`.

**Deliverables:**
- [ ] Create invoice (A/R) with line items, tax, and totals
- [ ] Create bill (A/P) with line items and totals
- [ ] Record partial / full payments against invoices or bills
- [ ] Update invoice/bill status automatically: `draft`, `open`, `paid`, `overdue`, `void`
- [ ] Aging report: current, 30, 60, 90, 90+ days overdue
- [ ] List invoices/bills with filters: status, contact, date range, is_bill
- [ ] Void an invoice/bill without deleting it (audit trail)
- [ ] Optionally link invoice payment to a bank transaction (post-reconciliation)
- [ ] Role check: `bookkeeper` or higher

**Acceptance tests:**
- `backend/tests/test_invoicing.py` ≥ 20 tests, all green
- Full backend regression: 0 failures

**Files to touch:**
- `backend/accounting/invoicing.py`
- `backend/routers/invoicing.py`
- `backend/models.py` (`Invoice`, `InvoiceLineItem`, `Payment` already exist; may need `linked_transaction_id`, `status` enum expansion)
- `alembic/versions/...` migration for any model changes
- `backend/tests/test_invoicing.py`
- `shared/tasks/v3.11.6/API-CONTRACT.md` (finalize Invoices/Bills/Payments section)

---

## Data Model (existing + proposed)

Existing models in `backend/models.py`:
- `Invoice` — `contact_name`, `invoice_number`, `issue_date`, `due_date`, `total`, `amount_paid`, `status`, `is_bill`
- `InvoiceLineItem` — `description`, `qty`, `rate`, `amount`
- `Payment` — `invoice_id`, `date`, `amount`, `method`

Proposed additions (if needed):
- `Invoice.linked_transaction_id` (FK to `transactions.id`, nullable) — ties a payment to a bank register transaction
- `Invoice.tax_amount` and `InvoiceLineItem.tax_amount` (optional; default 0)
- `Invoice.notes` (optional memo)
- `Payment.notes` (optional memo)

No changes required if we keep the model minimal for v3.11.6.

---

## API Endpoints

Build on the existing `backend/routers/invoicing.py`:

- `GET /api/invoices` — list invoices/bills
- `POST /api/invoices` — create invoice or bill (`is_bill` flag)
- `GET /api/invoices/{id}` — get single invoice/bill with line items and payments
- `PUT /api/invoices/{id}` — update draft invoice/bill
- `DELETE /api/invoices/{id}` — delete draft invoice/bill
- `POST /api/invoices/{id}/void` — void an open/paid invoice/bill
- `POST /api/invoices/{id}/payments` — record payment
- `DELETE /api/invoices/{id}/payments/{payment_id}` — reverse a payment
- `GET /api/invoices/aging` — A/R and A/P aging report

---

## Cross-Cutting Concerns

1. **Status enum collision.** Do not use `Transaction.status` for invoices. `Invoice.status` is self-contained: `draft`, `open`, `paid`, `overdue`, `void`.
2. **COA integration (optional).** When a payment is recorded, optionally create a corresponding register transaction tied to a cash/checking account and an income/expense COA account. This is a stretch goal for v3.11.6; defer if it increases scope.
3. **Tenant scoping.** All endpoints use `_wrap_tenant` and `tenant_id` filters.
4. **Migration discipline.** Any model addition gets a reversible Alembic migration with single head.
5. **API contract updates.** Update `API-CONTRACT.md` Invoices/Bills/Payments section.

---

## Parallel Execution with Track 6

Track 7 shares only the B1/B2 foundation. There is **no functional dependency** on Track 6. The two tracks can branch independently from `v3.11.6-dev` and merge back in any order.

**Coordination points:**
- Both tracks must use the same `_wrap_tenant` / tenant scoping pattern.
- Both tracks must keep Alembic migrations as a single head (merge after each track, run `alembic heads`, resolve if needed).
- B4.03 reports may later consume B5 aging data, but that is a B6/frontend concern, not a Track 7 blocker.

---

## Suggested Execution Order

1. Harden existing invoice/bill CRUD and tests
2. Add payment logic and automatic status transitions
3. Add aging report
4. Add void + audit-safe delete
5. Update API contract and full regression

---

## Definition of Done

- B5 module implemented and tested
- `backend/tests` regression passes (target: 0 failures)
- API contract updated
- Branch merged into `v3.11.6-dev`
- Daily memory log updated

---

## Assignment

- **Primary builder:** Jane
- **Validator:** glm-5.2:cloud (final full regression + code review)
- **Orchestrator approval:** James before merge
