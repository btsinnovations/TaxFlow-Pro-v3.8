# Bundle B4 — Financial Operations

**Goal:** Deliver reconciliation, tax exports, reports, and budgeting so the platform closes books and produces useful output.

---

## 3.11.6.B4.01 — Bank Reconciliation Backend

### Files
- `backend/accounting/reconciliation.py`
- `backend/routers/reconciliation.py`
- `backend/tests/test_reconciliation.py`

### Requirements
- `reconciliation_imports` table: account_id, import_date, statement_balance.
- `reconciliation_matches` table: import_id, transaction_id, match_type (`auto`, `manual`, `unmatched`).
- Import a statement (CSV/OFX) and auto-match by date + amount.
- Manual match/unmatch.
- Reconciliation report: cleared balance, statement balance, difference.
- Mark account as reconciled for a statement period.

### Tests
- Import OFX statement.
- Auto-match transactions.
- Manual match remaining.
- Mark reconciled.
- Detect difference and list unmatched.
- Tenant isolation.

---

## 3.11.6.B4.02 — Tax Filing Exports Backend

### Files
- `backend/accounting/tax_exports.py`
- `backend/routers/tax_exports.py`
- `backend/tests/test_tax_exports.py`

### Requirements
- Export formats: CSV, Excel, PDF summary.
- Export scopes: full GL, P&L, balance sheet, transaction detail, Schedule C mapping.
- Date-range filtering.
- Category mapping to tax lines.
- Signed export manifest (audit trail).

### Tests
- Generate P&L export.
- Generate balance sheet export.
- Schedule C mapping.
- Signed manifest present.
- Tenant isolation.

---

## 3.11.6.B4.03 — Reports Center Backend

### Files
- `backend/accounting/reports.py`
- `backend/routers/reports.py`
- `backend/tests/test_reports.py`

### Requirements
- Standard reports: P&L, Balance Sheet, Cash Flow, Trial Balance, General Ledger Detail.
- Period-based and YTD.
- Drill-down by account.
- Export to CSV/Excel/PDF.
- Caching of report results (optional, short TTL).

### Tests
- Generate each standard report.
- Period filter.
- Drill-down returns child transactions.
- Export formats.
- Tenant isolation.

---

## 3.11.6.B4.04 — Budget & Cash Flow Forecasting Backend

### Files
- `backend/accounting/budget.py`
- `backend/routers/budget.py`
- `backend/tests/test_budget.py`

### Requirements
- `budget_lines` table: category_id, period, amount.
- Budget vs. actual by category and period.
- Simple cash flow forecast based on recurring rules + historical averages.
- Variance alerts (over/under budget thresholds).
- Export budget template.

### Tests
- Create budget lines.
- Budget vs. actual report.
- Cash flow forecast.
- Variance alert.
- Tenant isolation.
