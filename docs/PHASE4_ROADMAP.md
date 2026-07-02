# TaxFlow Pro Phase 4 Roadmap — CPA-Grade Practice Tools

**Status:** Draft — pending Josh approval  
**Audience:** TaxFlow Pro product roadmap  
**Goal:** Move TaxFlow Pro from personal/small-biz local-first utility to a tool CPAs and accounting practices can use with clients.

---

## 1. Engagement & Client Management

### 1.1 Client Onboarding Checklist
- Track required documents per client (statements, receipts, prior-year filings)
- Persist checklist state in local DB
- Status endpoint for dashboard progress bar

### 1.2 Document Request Tracking
- Request list per client engagement
- Mark items received / missing / reviewed
- Due dates with local reminder hooks

### 1.3 Multi-Client Entity Switcher (Backend)
- `/api/clients/switch` endpoint
- Active client stored in session state
- All queries scoped to active client unless explicitly global

---

## 2. CPA Review Workflow

### 2.1 Reviewer Notes on Transactions
- Add `reviewer_notes` column to `transactions`
- POST / PATCH `/api/transactions/{id}/note`
- Notes appear in exports

### 2.2 Approval Status Flags
- Add `review_status` enum: `pending`, `flagged`, `approved`
- Bulk update endpoint: `POST /api/transactions/bulk-review`
- Dashboard summary by review status

### 2.3 Query / Flag Transactions
- Endpoint to flag transactions for client clarification
- Flagged items excluded from final tax summary until resolved

---

## 3. Trial Balance & Reconciliation

### 3.1 Bank Reconciliation Worksheet
- Endpoint that compares statement ending balance to sum of transactions
- Unreconciled difference reported with transaction list
- Support for manual adjustments with notes

### 3.2 Adjusting Journal Entries
- `POST /api/adjusting-entries`
- Entries linked to client and period
- Separate from imported transactions; included in reports

### 3.3 Debits = Credits Sanity Check
- Per-statement and per-account trial balance endpoint
- Return imbalance amount and suspect transactions

---

## 4. Tax Form Alignment

### 4.1 Schedule C / E / 8829 Line Mapping
- Category → tax line mapping table
- Configurable per client
- Year-end summary grouped by tax line

### 4.2 Depreciation Schedule Tracking
- Asset register table
- Simple straight-line depreciation calculation
- Link to asset purchase transactions

### 4.3 1099 / 1098-K Tracking
- Vendor/payee aggregation endpoint
- Threshold warnings ($600+ for 1099-NEC, etc.)

---

## 5. Reporting Exports

### 5.1 Accountant-Friendly Excel Workbooks
- Multi-sheet export: transactions, summary, notes, reconciliation
- Formulas preserved; formatted for review

### 5.2 QBO / Xero Accountant Copy Export
- IIF or CSV compatible with accountant imports
- Chart of accounts mapping per client

### 5.3 Standard Financial Statements
- P&L, Balance Sheet, Cash Flow
- Period-selectable (monthly, quarterly, annual)

---

## 6. Security & Compliance

### 6.1 Role-Based Permissions (Backend)
- Roles: owner, preparer, reviewer, view-only
- Permission checks on sensitive endpoints

### 6.2 Session Timeout Policy
- Configurable idle timeout
- Auto-lock backend after inactivity

### 6.3 Encrypted Export Password Protection
- Password-encrypt exported archives
- Require password confirmation before export

### 6.4 Audit Trail v2
- Immutable log of all changes: transaction edits, imports, backups, exports
- Tamper-evident with hash chain

### 6.5 Receipt Capture + Local OCR
- Camera or file upload for receipt images from the desktop app.
- Local OCR using Tesseract / PaddleOCR / DocLayout-YOLO; no cloud vision APIs.
- Extract line items, merchant, date, total, tax.
- Link receipt images to existing transactions or create new cash transactions.
- Store images and extracted text locally.

### 6.6 Anomaly Detection
- Statistical + rule-based flags on imported transactions.
- Detect duplicate transactions, unusual amounts compared to category history, off-hours activity, and missing recurring items.
- Rank transactions by anomaly score in a review queue.
- Exclude high-anomaly items from tax summaries until reviewed.

### 6.7 OFX Direct Connect
- Download statements directly from bank OFX servers where supported.
- No third-party aggregator; credentials stored encrypted locally.
- Configurable polling schedule, manual sync button, and per-bank enable/disable.
- Falls back to manual file upload for unsupported institutions.

---

## 7. Backend Deliverables Checklist

| # | Deliverable | Depends On |
|---|-------------|------------|
| 1 | Client onboarding + document tracking endpoints | `clients` table extensions |
| 2 | Reviewer notes + status flags on transactions | `transactions` schema update |
| 3 | Bulk review endpoint | #2 |
| 4 | Bank reconciliation worksheet endpoint | statement balance fields |
| 5 | Adjusting journal entries table + endpoints | new `adjusting_entries` table |
| 6 | Tax line mapping per client/category | new `tax_mappings` table |
| 7 | Depreciation register | new `assets` table |
| 8 | 1099/1098-K aggregation endpoint | payee normalization |
| 9 | Multi-sheet Excel export | openpyxl |
| 10 | Financial statement generation | aggregation engine |
| 11 | Role-based permissions | `users` roles extension |
| 12 | Audit trail hash chain | new `audit_log` table |
| 13 | Receipt capture + local OCR | new `receipts` table, image storage, OCR sandbox |
| 14 | Anomaly detection engine | transaction history + statistical heuristics |
| 15 | OFX Direct Connect | encrypted credentials, OFX client library, scheduler |

---

## 8. Out of Scope for Phase 4

- Desktop wrapper / native app (Phase 5)
- Cloud sync or SaaS hosting
- Live bank feeds / Plaid integration (OFX Direct Connect is local-only and in scope)
- Mobile app companion (Phase 5)

---

*Draft — awaiting Josh approval before implementation begins.*
