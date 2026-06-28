# TaxFlow Pro v3.11.6 — API Contract

**Status:** Draft for James review  
**Last updated:** 2026-06-27  
**Branch:** `v3.11.6-dev-PHASE1-TRACK2-B1-foundation`

---

## Conventions

- All endpoints are prefixed with `/api/`
- Authentication: `Authorization: Bearer <JWT>` header
- Multi-tenant header: `X-Tenant-ID: <client_id>` (PostgreSQL multi-entity mode only; SQLite single-user infers from auth)
- Content-Type: `application/json` for all POST/PUT/PATCH
- Dates: ISO 8601 (`YYYY-MM-DD`)
- Monetary amounts: numeric (e.g., `1234.56`)
- Error shape: `{"detail": "message"}` with appropriate HTTP status code

---

## 1. Chart of Accounts (COA)

### `GET /api/coa`
List all COA accounts for the current tenant.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "tenant_id": 1,
    "number": "1010",
    "name": "Operating Checking",
    "type": "asset",
    "parent_id": null,
    "is_active": true,
    "children": []
  }
]
```

### `POST /api/coa`
Create a new COA account. Requires **bookkeeper** role or higher.

**Request:**
```json
{
  "number": "1050",
  "name": "Petty Cash",
  "type": "asset",
  "parent_id": null,
  "is_active": true
}
```

**Response:** `201 Created`
```json
{
  "id": 2,
  "tenant_id": 1,
  "number": "1050",
  "name": "Petty Cash",
  "type": "asset",
  "parent_id": null,
  "is_active": true,
  "children": []
}
```

### `PUT /api/coa/{account_id}`
Update an existing COA account. Requires **bookkeeper** role or higher.

**Request (partial update):**
```json
{
  "name": "Petty Cash Reserve",
  "is_active": false
}
```

**Response:** `200 OK` — full account object

### `DELETE /api/coa/{account_id}`
Delete a COA account. Requires **admin** role or higher.

**Guards:** Cannot delete if referenced by transactions, ledger entries, categorization rules, or child accounts.

**Response:** `200 OK`
```json
{"ok": true}
```

**Error:** `409 Conflict` if account is referenced

### `POST /api/coa/seed`
Seed a standard small-business COA for the current tenant. Requires **admin** role or higher.

**Response:** `200 OK` — array of created accounts (34 standard accounts)

**Error:** `409 Conflict` if COA already seeded

### `PATCH /api/coa/{account_id}/renumber?new_number=1050`
Renumber an existing COA account. Requires **admin** role or higher.

Validates the new number is within the account's type range:
- Assets: 1000–1999
- Liabilities: 2000–2999
- Equity: 3000–3999
- Income: 4000–4999
- Expenses: 5000–9999

**Response:** `200 OK` — updated account object

**Error:** `422` if number out of range, `409` if number in use

### `PATCH /api/coa/{account_id}/parent?new_parent_id=3`
Reassign the parent of a COA account. Requires **admin** role or higher.

Pass `new_parent_id=0` or `null` to clear parent (make root).

**Response:** `200 OK` — updated account object

---

## 2. Transactions / Register

### `GET /api/transactions`
List transactions for the current tenant with optional filters.

**Query params:**
- `tenant_id` (int) — tenant filter (SQLite)
- `account_id` (int) — filter by bank account
- `limit` (int, default 50) — page size
- `offset` (int, default 0) — pagination
- `start_date` / `end_date` (date) — date range
- `category` (string) — category filter

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "date": "2026-01-15",
    "description": "Store Purchase",
    "amount": 42.50,
    "tx_type": "debit",
    "category": "uncategorized",
    "running_balance": 1057.50,
    "statement_id": 1,
    "tenant_id": 1,
    "coa_account_id": null,
    "workpaper_ref": null,
    "created_at": "2026-01-15T10:30:00Z"
  }
]
```

### `POST /api/transactions`
Create a transaction directly (not from statement import).

**Request:**
```json
{
  "date": "2026-01-15",
  "description": "Office Supplies",
  "amount": 42.50,
  "account_id": 1,
  "tx_type": "debit",
  "category": "Office Supplies",
  "coa_account_id": 2,
  "payee": "Staples",
  "memo": "Receipt #123"
}
```

**Response:** `200 OK` — transaction object

### `PUT /api/transactions/{id}`
Update a transaction's COA assignment, workpaper ref, or category.

**Response:** `200 OK` — updated transaction

### `DELETE /api/transactions/{id}`
Delete a transaction (cascades to ledger entries and flags).

**Response:** `200 OK`

### `POST /api/transactions/bulk-delete`
Bulk delete transactions.

**Request:**
```json
{
  "transaction_ids": [1, 2, 3]
}
```

---

## 3. Recurring Rules

### `GET /api/recurring`
List recurring rules for the current tenant.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "account_id": 1,
    "description": "Monthly Rent",
    "amount": 2000.00,
    "frequency": "monthly",
    "start_date": "2026-01-01",
    "end_date": null,
    "count": null,
    "is_active": true,
    "next_date": "2026-07-01",
    "tenant_id": 1,
    "created_at": "2026-01-01T00:00:00Z"
  }
]
```

### `POST /api/recurring`
Create a recurring rule.

**Request:**
```json
{
  "account_id": 1,
  "description": "Monthly Rent",
  "amount": 2000.00,
  "frequency": "monthly",
  "start_date": "2026-01-01",
  "end_date": null,
  "count": null,
  "splits": null
}
```

**Frequency enum:** `daily`, `weekly`, `bi_weekly`, `monthly`, `quarterly`, `yearly`, `custom`

### `PUT /api/recurring/{id}`
Update a recurring rule (partial update).

### `DELETE /api/recurring/{id}`
Delete a recurring rule.

### `POST /api/recurring/{id}/generate`
Generate the next occurrence transaction from a recurring rule.

---

## 4. Checks

### `GET /api/checks`
List checks for the current tenant.

### `POST /api/checks`
Create a check entry.

**Request:**
```json
{
  "date": "2026-01-15",
  "payee": "ABC Corp",
  "amount": 500.00,
  "account_id": 1,
  "check_number": "1001",
  "memo": "Invoice #123"
}
```

### `PUT /api/checks/{id}`
Update a check.

### `DELETE /api/checks/{id}`
Delete a check.

---

## 5. Inventory

### `GET /api/inventory`
List inventory items for the current tenant.

### `POST /api/inventory`
Create an inventory item.

**Request:**
```json
{
  "sku": "WIDGET-001",
  "name": "Widget",
  "valuation_method": "average",
  "qty_on_hand": 100,
  "unit_cost": 5.50
}
```

### `GET /api/inventory/{id}`
Get a single inventory item.

### `PUT /api/inventory/{id}`
Update an inventory item.

### `POST /api/inventory/{id}/transactions`
Record an inventory transaction (purchase, sale, adjustment).

**Request:**
```json
{
  "qty": 10,
  "unit_cost": 5.50,
  "type": "purchase"
}
```

---

## 6. FX (Multi-Currency)

### `GET /api/fx`
List FX rates for the current tenant.

### `POST /api/fx`
Create an FX rate entry.

**Request:**
```json
{
  "from_currency": "EUR",
  "to_currency": "USD",
  "rate": 1.0850,
  "effective_date": "2026-01-15",
  "source": "manual"
}
```

### `GET /api/fx/convert`
Convert an amount between currencies using the latest rate.

**Query params:** `from`, `to`, `amount`, `date` (optional)

**Response:**
```json
{
  "from_currency": "EUR",
  "to_currency": "USD",
  "rate": 1.0850,
  "amount": 100.00,
  "converted": 108.50,
  "effective_date": "2026-01-15"
}
```

---

## 7. Reconciliation

### `POST /api/reconciliation/imports`
Create a reconciliation import.

**Request:**
```json
{
  "account_id": 1,
  "import_date": "2026-01-15",
  "statement_date": "2026-01-31",
  "statement_balance": 5000.00,
  "filename": "jan_statement.csv"
}
```

### `GET /api/reconciliation/imports`
List reconciliation imports.

### `GET /api/reconciliation/imports/{id}/matches`
List matches for an import.

### `POST /api/reconciliation/imports/{id}/matches`
Create or update a match.

**Request:**
```json
{
  "ledger_tx_id": 42,
  "statement_tx_id": "STMT-001",
  "match_type": "auto",
  "status": "matched"
}
```

---

## 8. Reports

### `GET /api/reports/balance-sheet`
Generate a balance sheet report.

**Query params:** `as_of` (date), `tenant_id` (int)

**Response:**
```json
{
  "as_of": "2026-01-31",
  "assets": [{"account": "Cash", "balance": 5000.00}],
  "liabilities": [{"account": "AP", "balance": 1200.00}],
  "equity": [{"account": "Capital", "balance": 3800.00}]
}
```

### `GET /api/reports/income-statement`
Generate an income statement (P&L).

**Query params:** `start_date`, `end_date`, `tenant_id`

### `GET /api/reports/trial-balance`
Generate a trial balance.

**Query params:** `as_of` (date), `tenant_id`

### `GET /api/reports/cash-flow`
Generate a cash flow statement.

**Query params:** `start_date`, `end_date`, `tenant_id`

---

## 9. Budget

### `GET /api/budget`
List budget lines for the current tenant.

### `POST /api/budget`
Create a budget line.

**Request:**
```json
{
  "account_id": 1,
  "period": "2026-01",
  "budget_amount": 2000.00,
  "actual_amount": 1850.00
}
```

### `PUT /api/budget/{id}`
Update a budget line.

### `DELETE /api/budget/{id}`
Delete a budget line.

---

## 10. Invoicing / A/P / A/R (B5)

### `GET /api/invoicing/invoices`
List customer invoices (A/R). Supports filters: `?status=open`, `?contact=Acme`, `?start_date=2026-01-01`, `?end_date=2026-06-30`.

**Response:**
```json
[
  {
    "id": 1,
    "contact_name": "ABC Corp",
    "invoice_number": "INV-001",
    "issue_date": "2026-01-15",
    "due_date": "2026-02-15",
    "total": 1500.00,
    "amount_paid": 500.00,
    "balance": 1000.00,
    "status": "open",
    "aging_bucket": "current"
  }
]
```

### `GET /api/invoicing/bills`
List vendor bills (A/P). Same filters as invoices.

### `POST /api/invoicing/invoices`
Create a customer invoice (A/R). Requires `bookkeeper` role.

**Request:**
```json
{
  "contact_name": "ABC Corp",
  "invoice_number": "INV-001",
  "issue_date": "2026-01-15",
  "due_date": "2026-02-15",
  "line_items": [
    {"description": "Consulting", "qty": 10, "rate": 150.00}
  ]
}
```

**Response:** `{"id": 1, "total": 1500.00, "status": "open"}`

### `POST /api/invoicing/bills`
Create a vendor bill (A/P). Same shape as invoice creation.

**Response:** `{"id": 2, "total": 800.00, "status": "open", "is_bill": true}`

### `GET /api/invoicing/{invoice_id}`
Get a single invoice or bill with line items and payments.

**Response:**
```json
{
  "id": 1,
  "contact_name": "ABC Corp",
  "invoice_number": "INV-001",
  "issue_date": "2026-01-15",
  "due_date": "2026-02-15",
  "total": 1500.00,
  "amount_paid": 500.00,
  "balance": 1000.00,
  "status": "open",
  "is_bill": false,
  "line_items": [{"id": 1, "description": "Consulting", "qty": 10, "rate": 150, "amount": 1500}],
  "payments": [{"id": 1, "date": "2026-01-20", "amount": 500, "method": "check"}]
}
```

### `PUT /api/invoicing/{invoice_id}`
Update a draft or open invoice. Only `draft` and `open` status can be edited. Requires `bookkeeper` role.

**Request:** `{"contact_name": "Updated", "issue_date": "2026-01-20", "due_date": "2026-02-20", "line_items": [...]}`

### `DELETE /api/invoicing/{invoice_id}`
Delete a draft or open invoice. Rejects if payments exist. Requires `admin` role.

### `POST /api/invoicing/{invoice_id}/void`
Void an invoice or bill. Sets status to `void` — record preserved for audit trail. Requires `bookkeeper` role.

**Response:** `{"id": 1, "status": "void"}`

### `POST /api/invoicing/{invoice_id}/payments`
Record a partial or full payment. Auto-transitions status to `paid` when balance reached. Requires `bookkeeper` role.

**Request:**
```json
{
  "amount": 500.00,
  "payment_date": "2026-01-20",
  "method": "check"
}
```

**Response:** `{"id": 1, "total": 1500.00, "amount_paid": 500.00, "status": "open"}`

### `DELETE /api/invoicing/{invoice_id}/payments/{payment_id}`
Reverse (delete) a payment. Recalculates invoice status. Requires `admin` role.

**Response:** `{"id": 1, "amount_paid": 0.00, "status": "open"}`

### `GET /api/invoicing/aging`
Aging report for outstanding invoices or bills.

**Query params:** `?is_bill=false` (A/R) or `?is_bill=true` (A/P)

**Response:**
```json
{
  "buckets": {"current": 1000.00, "30": 200.00, "60": 0.00, "90": 0.00, "90+": 0.00},
  "total_outstanding": 1200.00,
  "count": 2
}
```

---

## 11. Liabilities (Loans / Credit Lines)

### `GET /api/liabilities`
List liability schedules.

### `POST /api/liabilities`
Create a loan schedule.

**Request:**
```json
{
  "account_id": 1,
  "original_principal": 50000.00,
  "rate": 0.0450,
  "term_months": 60,
  "start_date": "2026-01-01",
  "payment_amount": 932.21
}
```

### `GET /api/liabilities/{id}`
Get a loan schedule with amortization table.

---

## 12. Investments

### `GET /api/investments`
List investment lots.

### `POST /api/investments`
Create an investment lot.

**Request:**
```json
{
  "account_id": 1,
  "symbol": "AAPL",
  "shares": 100,
  "cost_basis": 150.00,
  "acquisition_date": "2026-01-15"
}
```

### `PUT /api/investments/{id}`
Update an investment lot (e.g., record sale).

**Request:**
```json
{
  "sale_date": "2026-06-15",
  "sale_proceeds": 180.00
}
```

---

## 13. Profiles & Roles

### `GET /api/profiles`
List profiles (clients) visible to the authenticated user.

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "name": "My Business",
    "email": "biz@example.com",
    "tax_id": "12-3456789",
    "user_id": 1,
    "created_at": "2026-01-01T00:00:00Z"
  }
]
```

### `GET /api/profiles/{id}`
Get a single profile. Requires **viewer** role or higher.

### `GET /api/profiles/{id}/members`
List members of a profile. Requires **viewer** role or higher.

**Response:**
```json
[
  {
    "id": 1,
    "user_id": 2,
    "profile_id": 1,
    "role": "bookkeeper",
    "created_at": "2026-01-01T00:00:00Z"
  }
]
```

### `POST /api/profiles/{id}/members`
Add a user to a profile. Requires **admin** role or higher.

**Request:**
```json
{
  "user_id": 3,
  "role": "viewer"
}
```

**Role enum:** `owner`, `admin`, `bookkeeper`, `viewer`

### `PATCH /api/profiles/{id}/members/{user_id}`
Update a member's role. Requires **admin** role or higher.

Promoting to **owner** requires the actor to be an owner.

### `DELETE /api/profiles/{id}/members/{user_id}`
Remove a member. Requires **admin** role or higher.

Removing an **owner** requires the actor to be an owner and at least one owner must remain.

---

## Role Hierarchy

| Role | Level | Permissions |
|------|-------|------------|
| owner | 40 | Full access + manage owners |
| admin | 30 | All operations except owner management |
| bookkeeper | 20 | Create/edit transactions, COA entries |
| viewer | 10 | Read-only access |

Higher roles implicitly satisfy lower-role checks. The implicit profile owner (`clients.user_id`) is always treated as **owner** even without an explicit membership row.

---

## Single-User Offline Mode

When `TAXFLOW_SINGLE_USER=true` (default for local/desktop):
- No `X-Tenant-ID` header required — tenant inferred from authenticated user's primary client
- Current user defaults to **owner** on all profiles they own
- RLS is application-level (SQLite) — no native database policies
- All role checks pass for the implicit owner

---

## PostgreSQL Multi-Entity Mode

When `DATABASE_URL` points to PostgreSQL and `TAXFLOW_SINGLE_USER=false`:
- `X-Tenant-ID` header required on all tenant-scoped endpoints
- Native RLS policies enforce tenant isolation at the database level
- Service-role bypass available for migrations and admin operations
- `taxflow.tenant_id` session variable set per-request by middleware

---

## B3.01 — Liabilities (Loans & Credit Lines)

### `POST /api/liabilities/loan-schedule`
Create a loan with amortization schedule.

**Request:**
```json
{
  "account_id": 1,
  "original_principal": 24000.00,
  "annual_rate": 0.0725,
  "term_months": 24,
  "start_date": "2026-01-01"
}
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "account_id": 1,
  "payment_amount": 1075.42,
  "schedule": [
    {"month": 1, "date": "2026-02-01", "payment": 1075.42, "interest": 145.00, "principal": 930.42, "balance": 23069.58}
  ]
}
```

### `GET /api/liabilities/loan-schedule`
List all loan schedules.

### `GET /api/liabilities/loan-schedule/{id}`
Get a loan schedule with full amortization table.

### `POST /api/liabilities/loan-schedule/{id}/payments`
Record a loan payment with principal/interest allocation.

**Request:**
```json
{"payment_date": "2026-02-01", "payment_amount": 1075.42}
```

### `GET /api/liabilities/loan-schedule/{id}/payments`
List all payments for a loan schedule.

### `GET /api/liabilities/loan-schedule/{id}/upcoming?months=3`
Get upcoming payment details.

### `POST /api/liabilities/credit-lines`
Create a revolving credit line.

**Request:**
```json
{
  "account_id": 1,
  "credit_limit": 5000.00,
  "annual_rate": 0.1899,
  "start_date": "2026-01-01"
}
```

### `GET /api/liabilities/credit-lines`
List all credit lines.

### `GET /api/liabilities/credit-lines/{id}`
Get credit line details with transaction history.

### `POST /api/liabilities/credit-lines/{id}/draw`
Draw on a credit line.

### `POST /api/liabilities/credit-lines/{id}/payment`
Make a payment on a credit line.

### `GET /api/liabilities/credit-lines/{id}/available`
Get available credit.

### `POST /api/liabilities/amortization`
Compute amortization schedule without saving.

---

## B3.02 — Investments

### `POST /api/investments/lots`
Create an investment lot (buy).

**Request:**
```json
{
  "account_id": 1,
  "symbol": "AAPL",
  "shares": 10.5,
  "cost_basis": 150.00,
  "acquisition_date": "2025-06-01"
}
```

### `POST /api/investments/{account_id}/sell`
Sell lots using FIFO cost basis.

**Request:**
```json
{
  "symbol": "AAPL",
  "shares": 3.0,
  "sale_date": "2026-01-01",
  "sale_price_per_share": 175.00
}
```

### `GET /api/investments/{account_id}/holdings`
Current open holdings grouped by symbol.

### `GET /api/investments/{account_id}/unrealized`
Unrealized gains using latest price snapshots.

### `GET /api/investments/{account_id}/cost-basis?year=2026`
Cost-basis report for tax exports (realized + open positions).

### `POST /api/investments/{account_id}/dividend`
Record a dividend event.

### `POST /api/investments/{account_id}/split`
Record a stock split (adjusts all open lots).

### `POST /api/investments/prices`
Add a manual price snapshot.

### `GET /api/investments/{account_id}/events?symbol=AAPL`
List investment events.

---

## B3.03 — Inventory & Project Tags

### `POST /api/inventory/`
Create an inventory item.

**Request:**
```json
{
  "sku": "WIDGET-01",
  "name": "Widget",
  "cogs_account_id": null,
  "income_account_id": null,
  "asset_account_id": null,
  "valuation_method": "average"
}
```

### `GET /api/inventory/`
List all inventory items.

### `GET /api/inventory/{id}`
Get item details.

### `PUT /api/inventory/{id}`
Update an item.

### `POST /api/inventory/{id}/adjust`
Record a purchase, sale, or adjustment.

**Request:**
```json
{"qty": 10.0, "unit_cost": 5.0, "type": "purchase"}
```

### `GET /api/inventory/{id}/transactions`
List inventory transactions for an item.

### `GET /api/inventory/{id}/valuation`
Current valuation (FIFO or average cost).

### `POST /api/inventory/tags/{transaction_id}`
Add a project tag to a transaction.

### `DELETE /api/inventory/tags/{transaction_id}?tag=project-alpha`
Remove a tag.

### `GET /api/inventory/tags`
List all tags with counts.

### `GET /api/inventory/tags/search?tag=project-alpha`
Search transactions by tag.

---

## B3.04 — Multi-Currency (FX)

### `POST /api/fx/rates`
Create a manual FX rate.

**Request:**
```json
{
  "from_currency": "USD",
  "to_currency": "EUR",
  "rate": 0.92,
  "effective_date": "2026-01-01"
}
```

### `GET /api/fx/rates?from_currency=USD&to_currency=EUR`
List FX rates with optional filters.

### `POST /api/fx/convert`
Convert an amount.

**Request:**
```json
{
  "amount": 500.0,
  "from_currency": "USD",
  "to_currency": "GBP",
  "as_of": "2026-01-15"
}
```

### `GET /api/fx/convert?from=USD&to=GBP&amount=500&as_of=2026-01-15`
Convert via query params.

### `POST /api/fx/transactions/{id}/foreign`
Attach foreign currency info to a transaction.

### `POST /api/fx/transactions/{id}/settle`
Calculate FX gain/loss on settlement.

### `GET /api/fx/report?start_date=2026-01-01&end_date=2026-12-31`
Home-currency report of all foreign-currency transactions.