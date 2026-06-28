# TaxFlow Pro v3.11.6 — Track 6 Masterplan (B4 Financial Operations)

**Branch:** `v3.11.6-dev-PHASE3-TRACK6-financial-operations`  
**Cut from:** `v3.11.6-dev` (after Track 5 merge)  
**Goal:** Deliver production-grade bank reconciliation, financial reports, tax exports, and budgeting.

---

## Why Track 6 Exists

B1–B3 built the data model, register engine, and asset/liability/FX modules. Track 6 layers the operational bookkeeping workflows on top: reconciling bank statements, producing financial statements, exporting tax forms, and budgeting against actuals. These are the four must-have B4 modules.

---

## Modules & Acceptance Criteria

### B4.01 — Bank Reconciliation Backend

**Current state:** skeleton exists (`backend/accounting/reconciliation.py`, `backend/routers/reconciliation.py`, `backend/tests/test_reconciliation.py`); tests pass but coverage is thin.

**Deliverables:**
- [ ] Import a bank statement into a reconciliation session (`POST /api/reconciliation/import`)
- [ ] Auto-match statement rows to ledger transactions by amount ± tolerance and date window
- [ ] Manual match / unmatch endpoints
- [ ] Reconciliation status endpoint: statement balance, cleared, outstanding, difference
- [ ] Flag unmatched transactions and unmatched statement rows
- [ ] Role check: `bookkeeper` or higher

**Acceptance tests:**
- `backend/tests/test_reconciliation.py` ≥ 15 tests, all green
- Full backend regression: 0 failures

**Files to touch:**
- `backend/accounting/reconciliation.py`
- `backend/routers/reconciliation.py`
- `backend/models.py` (add `is_reconciled` flag on `Transaction`? reuse `ReconciliationMatch`?)
- `alembic/versions/...` migration for any model changes
- `backend/tests/test_reconciliation.py`
- `shared/tasks/v3.11.6/API-CONTRACT.md` (update Reconciliation section)

---

### B4.02 — Tax Filing Exports Backend

**Current state:** skeleton exists (`backend/accounting/tax_exports.py`, `backend/routers/tax_exports.py`, `backend/tests/test_tax_exports.py`); supports Schedule C line mapping only.

**Deliverables:**
- [ ] Schedule C export with line mappings driven by `TaxLineMapping`
- [ ] 1099-NEC / 1099-MISC export for contractor payments (annual summary by vendor)
- [ ] Year-end summary export (P&L + balance sheet + line-item Schedule C)
- [ ] Export formats: JSON + CSV
- [ ] Role check: `bookkeeper` or higher; `admin` or higher to edit mappings

**Acceptance tests:**
- `backend/tests/test_tax_exports.py` ≥ 12 tests, all green
- Full backend regression: 0 failures

**Files to touch:**
- `backend/accounting/tax_exports.py`
- `backend/routers/tax_exports.py`
- `backend/tests/test_tax_exports.py`
- `shared/tasks/v3.11.6/API-CONTRACT.md` (expand Tax Exports section)

---

### B4.03 — Reports Center Backend

**Current state:** skeleton exists (`backend/accounting/reports.py`, `backend/routers/reports.py`, `backend/tests/test_reports.py`); only P&L and bare-bones trial balance exist.

**Deliverables:**
- [ ] Profit & Loss (income statement) by date range, summarized by COA type
- [ ] Trial Balance as of date, grouped by COA account (debits/credits balance)
- [ ] Balance Sheet as of date (assets, liabilities, equity)
- [ ] Cash Flow Statement (operating/investing/financing) for date range
- [ ] Reports respect COA hierarchy (roll child accounts into parent totals)
- [ ] Role check: `viewer` or higher

**Acceptance tests:**
- `backend/tests/test_reports.py` ≥ 20 tests, all green
- Full backend regression: 0 failures

**Files to touch:**
- `backend/accounting/reports.py`
- `backend/routers/reports.py`
- `backend/tests/test_reports.py`
- `shared/tasks/v3.11.6/API-CONTRACT.md` (expand Reports section)

---

### B4.04 — Budget & Cash Flow Forecasting Backend

**Current state:** skeleton exists (`backend/accounting/budget.py`, `backend/routers/budget.py`, `backend/tests/test_budget.py`); budget lines exist but actuals are not pulled from transactions.

**Deliverances:**
- [ ] Set / update budget lines per COA account and period (`YYYY-MM`)
- [ ] Budget vs Actual report for date range
- [ ] 13-week cash flow forecast using recurring rules + open invoices/bills
- [ ] Variance alerts when actual exceeds budget by threshold (optional)
- [ ] Role check: `bookkeeper` or higher

**Acceptance tests:**
- `backend/tests/test_budget.py` ≥ 15 tests, all green
- Full backend regression: 0 failures

**Files to touch:**
- `backend/accounting/budget.py`
- `backend/routers/budget.py`
- `backend/models.py` ( BudgetLine already exists; verify no changes needed)
- `backend/tests/test_budget.py`
- `shared/tasks/v3.11.6/API-CONTRACT.md` (expand Budget section)

---

## Cross-Cutting Concerns

1. **Use COA, not GLAccount, as primary account reference.** B1 made `coa_accounts` the canonical chart. Reports, budget, and tax exports must read from `CoaAccount`. Legacy `GLAccount` remains for backward compatibility.
2. **Status field collision with B5 invoices.** `Transaction.status` is used by B2 for bulk status changes (pending/cleared/etc.). Do not overload it for reconciliation. Use `ReconciliationMatch` and a dedicated `reconciliation_status` concept.
3. **Tenant scoping.** All endpoints must use `_wrap_tenant` pattern and `tenant_id` filters. PostgreSQL RLS path must be verified with `TEST_DATABASE_URL`.
4. **Migration discipline.** Any model change gets a reversible Alembic migration with a single head.
5. **API contract updates.** Update `API-CONTRACT.md` as endpoints are finalized.

---

## Suggested Execution Order

1. Reports center — unlocks immediate value from existing B1/B2/B3 data
2. Bank reconciliation — highest user workflow value
3. Tax exports — depends on clean categorization + COA mappings
4. Budget / cash flow — can run parallel to tax exports after reconciliation

---

## Definition of Done

- All four B4 modules implemented and tested
- `backend/tests` regression passes (target: 0 failures, existing warnings acceptable)
- API contract updated
- Branch merged into `v3.11.6-dev`
- Daily memory log updated

---

## Notes

- Track 6 should be assigned to Jane as the primary builder.
- glm-5.2:cloud validator can run the final full regression and review.
- Keep frontend (B6) out of scope for this track; B6 will consume these endpoints later.
