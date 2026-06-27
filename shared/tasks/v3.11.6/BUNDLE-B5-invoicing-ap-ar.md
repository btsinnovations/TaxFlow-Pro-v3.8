# Bundle B5 — Invoicing & A/P / A/R

**Goal:** Add lightweight invoice, bill, and payment tracking for small-business workflows.

---

## 3.11.6.B5.01 — Lightweight Invoicing / A/P / A/R Backend

### Files
- `backend/accounting/invoicing.py`
- `backend/routers/invoicing.py`
- `backend/tests/test_invoicing.py`

### Requirements
- Invoices (A/R): customer, line items, terms, due date, status (draft/sent/paid/overdue).
- Bills (A/P): vendor, line items, due date, status (unpaid/paid/overdue).
- Payments linked to invoices/bills.
- Aging report: current, 30, 60, 90+ days.
- Simple PDF generation of invoice (html2canvas/jsPDF frontend path; backend provides data).
- No live email sending; export/share handled by OS.

### Tests
- Create invoice.
- Record payment against invoice.
- Create bill and mark paid.
- Aging report.
- Overdue detection.
- Tenant isolation.
