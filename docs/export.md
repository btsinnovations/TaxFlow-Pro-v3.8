# TaxFlow Pro v3.9 — CSV Export

## Overview

v3.9 provides five CSV exports under `/api/export` for bookkeeping and tax workflows. All exports are tenant-scoped and local-only; no data leaves the machine.

## Endpoints

| Endpoint | Purpose | Key query params |
|----------|---------|------------------|
| `GET /api/export/transactions` | Every transaction for the tenant, optionally date-filtered | `tenant_id`, `start_date`, `end_date` |
| `GET /api/export/general-ledger` | GL entries with debit/credit accounts and workpaper refs | `tenant_id` |
| `GET /api/export/trial-balance` | Account balances as of a given date | `tenant_id`, `as_of` |
| `GET /api/export/profit-loss` | Income/expense activity over a date range | `tenant_id`, `start_date`, `end_date` |
| `GET /api/export/balance-sheet` | Asset/liability/equity balances as of a date | `tenant_id`, `as_of` |

## Column layouts

### Transactions
`id`, `date`, `description`, `amount`, `type`, `category`, `workpaper_ref`, `gl_account_id`

### General ledger
`id`, `date`, `description`, `debit_account_id`, `credit_account_id`, `amount`, `memo`, `workpaper_ref`

### Trial balance, balance sheet
`account_id`, `code`, `name`, `account_type`, `balance`

### Profit & loss
`account_id`, `code`, `name`, `account_type`, `amount` plus a synthetic "Net Income" summary row.

## Implementation notes

- CSVs are built by `backend/services/export.py` using Python's built-in `csv` module and returned as `text/csv; charset=utf-8`.
- Decimal amounts are rendered as strings to preserve precision.
- P&L and balance-sheet outputs aggregate GL entries by `account_type`.
- `workpaper_ref` values are included directly in the transaction and general-ledger exports.

## Authentication

All export endpoints require a valid JWT in the `Authorization: Bearer <token>` header and enforce tenant scoping via `get_current_user`.
