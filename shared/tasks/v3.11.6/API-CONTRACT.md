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

## 10. Invoices / Bills / Payments

### `GET /api/invoices`
List invoices. Filter with `?is_bill=true` for bills (A/P) or `?is_bill=false` for invoices (A/R).

### `POST /api/invoices`
Create an invoice or bill.

**Request:**
```json
{
  "contact_name": "ABC Corp",
  "invoice_number": "INV-001",
  "issue_date": "2026-01-15",
  "due_date": "2026-02-15",
  "is_bill": false,
  "line_items": [
    {"description": "Consulting", "qty": 10, "rate": 150.00, "amount": 1500.00}
  ]
}
```

### `GET /api/invoices/{id}`
Get a single invoice with line items and payments.

### `PUT /api/invoices/{id}`
Update an invoice.

### `DELETE /api/invoices/{id}`
Delete an invoice.

### `POST /api/invoices/{id}/payments`
Record a payment against an invoice.

**Request:**
```json
{
  "date": "2026-01-20",
  "amount": 500.00,
  "method": "check"
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

## B2 — Transaction Engine Endpoints (v3.11.6)

### B2.01 — Unified Register

#### `GET /api/transactions/`
List transactions with enhanced filters, sorting, and pagination.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `account_id` | int | Filter by bank/credit account |
| `tenant_id` | int | Tenant override (admin) |
| `q` | string | Case-insensitive description search |
| `start_date` | date | Inclusive date range start |
| `end_date` | date | Inclusive date range end |
| `min_amount` | float | Minimum transaction amount |
| `max_amount` | float | Maximum transaction amount |
| `tags` | string | Comma-separated tag filter (any match) |
| `status` | string | `pending` \| `cleared` \| `reconciled` |
| `sort_by` | string | `date` \| `amount` \| `description` \| `account` |
| `sort_order` | string | `asc` \| `desc` |
| `limit` | int | Page size (default 100) |
| `offset` | int | Page offset (default 0) |

**Response:** `200 OK` — array of Transaction objects with `splits`, `tags`, `status` fields.

#### `POST /api/transactions/bulk-delete`
Bulk delete transactions.
**Body:** `{"transaction_ids": [int, ...]}`
**Response:** `{"deleted": int}`

#### `POST /api/transactions/bulk-tag`
Bulk add tags to transactions.
**Body:** `{"transaction_ids": [int, ...], "tags": [string, ...]}`
**Response:** `{"updated": int}`

#### `POST /api/transactions/bulk-status`
Bulk change status on transactions.
**Body:** `{"transaction_ids": [int, ...], "status": string}`
**Response:** `{"updated": int}`

#### `PATCH /api/transactions/{id}/status`
Set transaction status.
**Body:** `{"status": "pending"|"cleared"|"reconciled"}`
**Response:** `{"id": int, "status": string}`

### B2.02 — Transaction Splits

#### `GET /api/transactions/{id}/splits`
Get the splits for a transaction.
**Response:** `200 OK` — array of split objects: `{"account_id": int, "amount": float, "memo": string?}`

#### `PUT /api/transactions/{id}/splits`
Set splits on a transaction after validation.
**Body:** `{"splits": [{"account_id": int, "amount": float, "memo": string?, "category": string?}]}`
**Validation:** Sum of split amounts must equal transaction total. No empty accounts, no zero amounts, no duplicate splits.
**Response:** `{"id": int, "splits": [...]}`

#### `POST /api/transactions/{id}/splits/migrate`
Migrate a single-line transaction to have a one-entry split.
**Response:** `{"id": int, "splits": [...]}`

### B2.03 — Recurring / Scheduled Transactions

#### `POST /api/recurring/{rule_id}/generate?target_date=YYYY-MM-DD`
Generate pending occurrences for a recurring rule up to `target_date`. Idempotent — calling twice with the same date produces no duplicates.
**Response:** `{"occurrences": [{"scheduled_date": string, "description": string, "amount": float, "status": "pending", "rule_id": int}], "count": int}`

#### `POST /api/recurring/{rule_id}/materialize?as_of=YYYY-MM-DD`
Materialize real transaction(s) from a recurring rule.
**Response:** `{"materialized": int, "transactions": [...]}`

**Frequencies supported:** daily, weekly, biweekly, monthly, quarterly, yearly.

### B2.04 — Check Register

#### `POST /api/checks/`
Record a new check.
**Body:** `{"account_id": int, "check_number": string, "payee": string, "amount": float, "date": date, "memo": string?, "transaction_id": int?}`
**Response:** `201 Created` — Check object.
**Errors:** `409 Conflict` — Duplicate check number for account.

#### `GET /api/checks/`
List checks with optional filters.
**Query Parameters:** `account_id`, `start_number`, `end_number`, `status`
**Response:** `200 OK` — array of Check objects.

#### `GET /api/checks/{check_id}`
Get a single check by ID.

#### `PUT /api/checks/{check_id}`
Update a check entry.
**Body:** `{"payee": string?, "amount": float?, "date": date?, "memo": string?, "status": string?, "transaction_id": int?}`

#### `PATCH /api/checks/{check_id}/clear`
Mark a check as cleared.

#### `PATCH /api/checks/{check_id}/reconcile`
Mark a check as reconciled.

#### `PATCH /api/checks/{check_id}/void`
Void a check.
**Body:** `{"reason": string?}`

#### `DELETE /api/checks/{check_id}`
Delete a check entry.

#### `GET /api/checks/search/range?account_id=int&start=string&end=string`
Search checks by check number range (inclusive).

#### `POST /api/checks/issue`
Legacy: Issue a check (creates both a Check record and a Transaction).
**Body:** `{"account_id": int, "payee": string, "amount": float, "date": date, "memo": string?, "check_number": string?}`
**Response:** `201 Created` — Transaction object.