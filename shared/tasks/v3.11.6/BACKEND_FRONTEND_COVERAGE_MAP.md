# Backend → Frontend Coverage Map

**Generated:** 2026-06-29

## Summary

- Total backend endpoints: **197**
- Covered by frontend code: **154**
- Backend-only (no frontend consumer): **2**
- Unique frontend API routes found: **171**

## Legend

- ✅ = Frontend calls this endpoint (string match in `frontend/src/**`)
- ❌ = No frontend consumer found

## By Module

| Module | Endpoint | Method | Frontend |
|--------|----------|--------|----------|
| accounts | `GET /api/accounts/` | GET | ✅ |
| accounts | `POST /api/accounts/` | POST | ✅ |
| accounts | `PATCH /api/accounts/{account_id}` | PATCH | ✅ |
| accounts | `GET /api/accounts/{account_id}` | GET | ✅ |
| accounts | `DELETE /api/accounts/{account_id}` | DELETE | ✅ |
| audit | `GET /api/audit/` | GET | ✅ |
| audit | `GET /api/audit/logs` | GET | ✅ |
| audit | `GET /api/audit/verify` | GET | ✅ |
| auth | `GET /api/auth/status` | GET | ✅ |
| auth | `POST /api/auth/boot` | POST | ✅ |
| auth | `POST /api/auth/register` | POST | ✅ |
| auth | `POST /api/auth/login` | POST | ✅ |
| auth | `POST /api/auth/login-json` | POST | ✅ |
| auth | `POST /api/auth/refresh` | POST | ✅ |
| auth | `POST /api/auth/change-password` | POST | ✅ |
| auth | `GET /api/auth/me` | GET | ✅ |
| auth | `POST /api/auth/logout` | POST | ✅ |
| backup | `POST /api/backup/import` | POST | ✅ |
| backup | `GET /api/backup/export` | GET | ✅ |
| budget | `POST /api/budget/lines` | POST | ✅ |
| budget | `GET /api/budget/{period}/vs-actual` | GET | ✅ |
| budget | `GET /api/budget/cash-flow` | GET | ✅ |
| budget | `GET /api/budget/cash-flow-13-week` | GET | ✅ |
| budget | `GET /api/budget/{period}/variance-alerts` | GET | ✅ |
| checks | `GET /api/checks/{account_id}` | GET | ✅ |
| checks | `POST /api/checks/` | POST | ✅ |
| checks | `PATCH /api/checks/{transaction_id}/void` | PATCH | ✅ |
| clients | `GET /api/clients/` | GET | ✅ |
| clients | `POST /api/clients/` | POST | ✅ |
| clients | `GET /api/clients/{client_id}` | GET | ✅ |
| clients | `PATCH /api/clients/{client_id}` | PATCH | ✅ |
| clients | `DELETE /api/clients/{client_id}` | DELETE | ✅ |
| coa | `GET /api/coa/coa` | GET | ✅ |
| coa | `POST /api/coa/coa` | POST | ✅ |
| coa | `PUT /api/coa/coa/{account_id}` | PUT | ✅ |
| coa | `DELETE /api/coa/coa/{account_id}` | DELETE | ✅ |
| coa | `POST /api/coa/coa/seed` | POST | ✅ |
| coa | `PATCH /api/coa/coa/{account_id}/renumber` | PATCH | ✅ |
| coa | `PATCH /api/coa/coa/{account_id}/parent` | PATCH | ✅ |
| dashboard | `GET /api/dashboard/stats` | GET | ✅ |
| dashboard | `GET /api/dashboard/` | GET | ✅ |
| depreciation | `GET /api/depreciation/` | GET | ✅ |
| depreciation | `POST /api/depreciation/` | POST | ✅ |
| depreciation | `GET /api/depreciation/{asset_id}` | GET | ✅ |
| depreciation | `PATCH /api/depreciation/{asset_id}` | PATCH | ✅ |
| depreciation | `DELETE /api/depreciation/{asset_id}` | DELETE | ✅ |
| export | `GET /api/export/transactions` | GET | ✅ |
| export | `GET /api/export/general-ledger` | GET | ✅ |
| export | `GET /api/export/trial-balance` | GET | ✅ |
| export | `GET /api/export/profit-loss` | GET | ✅ |
| export | `GET /api/export/balance-sheet` | GET | ✅ |
| export | `GET /api/export/formats` | GET | ✅ |
| export | `GET /api/export/statement/{statement_id}` | GET | ✅ |
| flags | `GET /api/flags/` | GET | ✅ |
| flags | `POST /api/flags/` | POST | ✅ |
| flags | `GET /api/flags/{flag_id}` | GET | ✅ |
| flags | `PUT /api/flags/{flag_id}/resolve` | PUT | ✅ |
| flags | `DELETE /api/flags/{flag_id}` | DELETE | ✅ |
| fx | `POST /api/fx/rates` | POST | ✅ |
| fx | `GET /api/fx/rates` | GET | ✅ |
| fx | `POST /api/fx/convert` | POST | ✅ |
| fx | `GET /api/fx/convert` | GET | ✅ |
| fx | `POST /api/fx/transactions/{transaction_id}/foreign` | POST | ✅ |
| fx | `POST /api/fx/transactions/{transaction_id}/settle` | POST | ✅ |
| fx | `GET /api/fx/report` | GET | ✅ |
| gl | `POST /api/ledger/accounts` | POST | ✅ |
| gl | `GET /api/ledger/accounts` | GET | ✅ |
| gl | `POST /api/ledger/entries` | POST | ✅ |
| gl | `POST /api/ledger/adjusting-entry` | POST | ✅ |
| gl | `PUT /api/ledger/entries/{entry_id}/workpaper-ref` | PUT | ✅ |
| gl | `POST /api/ledger/auto-post-batch` | POST | ✅ |
| health | `GET /api/health/migrations` | GET | ✅ |
| health | `GET /api/health/public` | GET | ✅ |
| health | `GET /api/health/config` | GET | ✅ |
| health | `GET /api/health/bootstrap` | GET | ✅ |
| health | `GET /api/health/echo-auth` | GET | ✅ |
| imports | `POST /api/imports/detect` | POST | ✅ |
| imports | `POST /api/imports/ofx` | POST | ✅ |
| inventory | `POST /api/inventory/tags/{transaction_id}` | POST | ✅ |
| inventory | `DELETE /api/inventory/tags/{transaction_id}` | DELETE | ✅ |
| inventory | `GET /api/inventory/tags` | GET | ✅ |
| inventory | `GET /api/inventory/tags/search` | GET | ✅ |
| inventory | `GET /api/inventory/` | GET | ✅ |
| inventory | `POST /api/inventory/` | POST | ✅ |
| inventory | `GET /api/inventory/{item_id}` | GET | ✅ |
| inventory | `PUT /api/inventory/{item_id}` | PUT | ✅ |
| inventory | `POST /api/inventory/{item_id}/adjust` | POST | ✅ |
| inventory | `GET /api/inventory/{item_id}/transactions` | GET | ✅ |
| inventory | `GET /api/inventory/{item_id}/valuation` | GET | ✅ |
| investments | `POST /api/investments/lots` | POST | ✅ |
| investments | `POST /api/investments/{account_id}/sell` | POST | ✅ |
| investments | `GET /api/investments/{account_id}/holdings` | GET | ✅ |
| investments | `POST /api/investments/{account_id}/dividend` | POST | ✅ |
| investments | `POST /api/investments/{account_id}/split` | POST | ✅ |
| investments | `POST /api/investments/prices` | POST | ✅ |
| investments | `GET /api/investments/{account_id}/unrealized` | GET | ✅ |
| investments | `GET /api/investments/{account_id}/cost-basis` | GET | ✅ |
| investments | `GET /api/investments/{account_id}/events` | GET | ✅ |
| invoicing | `GET /api/invoicing/invoices` | GET | ✅ |
| invoicing | `GET /api/invoicing/bills` | GET | ✅ |
| invoicing | `POST /api/invoicing/invoices` | POST | ✅ |
| invoicing | `POST /api/invoicing/bills` | POST | ✅ |
| invoicing | `GET /api/invoicing/aging` | GET | ✅ |
| invoicing | `GET /api/invoicing/{invoice_id}` | GET | ✅ |
| invoicing | `PUT /api/invoicing/{invoice_id}` | PUT | ✅ |
| invoicing | `DELETE /api/invoicing/{invoice_id}` | DELETE | ✅ |
| invoicing | `POST /api/invoicing/{invoice_id}/void` | POST | ✅ |
| invoicing | `POST /api/invoicing/{invoice_id}/payments` | POST | ✅ |
| invoicing | `DELETE /api/invoicing/{invoice_id}/payments/{payment_id}` | DELETE | ✅ |
| liabilities | `POST /api/liabilities/loan-schedule` | POST | ✅ |
| liabilities | `GET /api/liabilities/loan-schedule` | GET | ✅ |
| liabilities | `GET /api/liabilities/loan-schedule/{schedule_id}` | GET | ✅ |
| liabilities | `POST /api/liabilities/loan-schedule/{schedule_id}/payments` | POST | ✅ |
| liabilities | `GET /api/liabilities/loan-schedule/{schedule_id}/payments` | GET | ✅ |
| liabilities | `GET /api/liabilities/loan-schedule/{schedule_id}/upcoming` | GET | ✅ |
| liabilities | `POST /api/liabilities/credit-lines` | POST | ✅ |
| liabilities | `GET /api/liabilities/credit-lines` | GET | ✅ |
| liabilities | `GET /api/liabilities/credit-lines/{cl_id}` | GET | ✅ |
| liabilities | `POST /api/liabilities/credit-lines/{cl_id}/draw` | POST | ✅ |
| liabilities | `POST /api/liabilities/credit-lines/{cl_id}/payment` | POST | ✅ |
| liabilities | `GET /api/liabilities/credit-lines/{cl_id}/available` | GET | ✅ |
| liabilities | `POST /api/liabilities/amortization` | POST | ✅ |
| mileage | `POST /api/mileage/logs` | POST | ✅ |
| mileage | `GET /api/mileage/logs` | GET | ✅ |
| mileage | `GET /api/mileage/summary` | GET | ✅ |
| ml | `GET /api/ml/status` | GET | ✅ |
| ml | `POST /api/ml/toggle` | POST | ✅ |
| ml | `POST /api/ml/train` | POST | ✅ |
| ml | `GET /api/ml/model-info` | GET | ✅ |
| ml | `POST /api/ml/categorize/{statement_id}` | POST | ✅ |
| periods | `POST /api/periods/{period_id}/close` | POST | ✅ |
| periods | `POST /api/periods/{period_id}/reopen` | POST | ✅ |
| periods | `GET /api/periods/{period_id}/status` | GET | ✅ |
| profiles | `GET /api/profiles/` | GET | ✅ |
| profiles | `GET /api/profiles/{profile_id}` | GET | ✅ |
| profiles | `GET /api/profiles/{profile_id}/members` | GET | ✅ |
| profiles | `POST /api/profiles/{profile_id}/members` | POST | ✅ |
| profiles | `PATCH /api/profiles/{profile_id}/members/{user_id}` | PATCH | ✅ |
| profiles | `DELETE /api/profiles/{profile_id}/members/{user_id}` | DELETE | ✅ |
| reconciliation | `POST /api/reconciliation/import` | POST | ✅ |
| reconciliation | `POST /api/reconciliation/{import_id}/auto-match` | POST | ✅ |
| reconciliation | `POST /api/reconciliation/{import_id}/manual-match` | POST | ✅ |
| reconciliation | `POST /api/reconciliation/{import_id}/unmatch` | POST | ✅ |
| reconciliation | `GET /api/reconciliation/{import_id}/unmatched` | GET | ✅ |
| reconciliation | `GET /api/reconciliation/{import_id}/matches` | GET | ✅ |
| reconciliation | `GET /api/reconciliation/{import_id}/status` | GET | ✅ |
| reconciliation | `POST /api/reconciliation/{import_id}/complete` | POST | ✅ |
| reconciliation | `POST /api/reconciliation/{import_id}/reopen` | POST | ✅ |
| recurring | `GET /api/recurring/` | GET | ✅ |
| recurring | `POST /api/recurring/` | POST | ✅ |
| recurring | `PUT /api/recurring/{rule_id}` | PUT | ✅ |
| recurring | `DELETE /api/recurring/{rule_id}` | DELETE | ✅ |
| recurring | `POST /api/recurring/{rule_id}/materialize` | POST | ✅ |
| reports | `POST /api/reports/profit-and-loss` | POST | ✅ |
| reports | `POST /api/reports/trial-balance` | POST | ✅ |
| reports | `POST /api/reports/balance-sheet` | POST | ✅ |
| reports | `POST /api/reports/cash-flow` | POST | ✅ |
| rules | `GET /api/rules/` | GET | ✅ |
| rules | `POST /api/rules/` | POST | ✅ |
| rules | `GET /api/rules/{rule_id}` | GET | ✅ |
| rules | `PUT /api/rules/{rule_id}` | PUT | ✅ |
| rules | `DELETE /api/rules/{rule_id}` | DELETE | ✅ |
| sales_tax | `POST /api/sales-tax/rates` | POST | ✅ |
| sales_tax | `GET /api/sales-tax/rates` | GET | ✅ |
| sales_tax | `POST /api/sales-tax/payments` | POST | ✅ |
| sales_tax | `GET /api/sales-tax/payments` | GET | ✅ |
| sales_tax | `GET /api/sales-tax/liability-summary` | GET | ✅ |
| tax | `GET /api/tax/` | GET | ✅ |
| tax | `PATCH /api/tax/{rule_id}` | PATCH | ✅ |
| tax | `GET /api/tax/summary/{year}` | GET | ✅ |
| tax_exports | `POST /api/tax-exports/schedule-c` | POST | ✅ |
| tax_exports | `GET /api/tax-exports/lines` | GET | ✅ |
| tax_exports | `POST /api/tax-exports/1099` | POST | ✅ |
| tax_exports | `POST /api/tax-exports/year-end-summary` | POST | ✅ |
| tax_exports | `GET /api/tax-exports/year-end-package` | GET | ✅ |
| tax_exports | `POST /api/tax-exports/form-1065` | POST | ✅ |
| tax_exports | `POST /api/tax-exports/form-1120s` | POST | ✅ |
| tax_exports | `POST /api/tax-exports/form-8825` | POST | ✅ |
| tax_exports | `POST /api/tax-exports/schedule-e` | POST | ✅ |
| tax_exports | `POST /api/tax-exports/form-4562` | POST | ✅ |
| tax_exports | `POST /api/tax-exports/mappings` | POST | ✅ |
| tax_exports | `DELETE /api/tax-exports/mappings/{mapping_id}` | DELETE | ✅ |
| tax_exports | `GET /api/tax-exports/mappings` | GET | ✅ |
| tests | `GET /api/tests/` | GET | ❌ |
| tests | `POST /api/tests/run` | POST | ❌ |
| transactions | `GET /api/transactions/` | GET | ✅ |
| transactions | `POST /api/transactions/` | POST | ✅ |
| transactions | `PATCH /api/transactions/{transaction_id}` | PATCH | ✅ |
| transactions | `DELETE /api/transactions/{transaction_id}` | DELETE | ✅ |
| transactions | `GET /api/transactions/{transaction_id}/running-balance` | GET | ✅ |
| transactions | `PUT /api/transactions/{transaction_id}/workpaper-ref` | PUT | ✅ |
| upload | `POST /api/upload/` | POST | ✅ |
| vendors | `POST /api/vendors` | POST | ✅ |
| vendors | `GET /api/vendors` | GET | ✅ |
| vendors | `GET /api/vendors/{vendor_id}` | GET | ✅ |
| vendors | `PUT /api/vendors/{vendor_id}` | PUT | ✅ |
| year_end | `POST /api/year-end/close` | POST | ✅ |

## Backend-only Endpoints (no frontend consumer)

- `/api/tests/`
- `/api/tests/run`

## Frontend Routes Found

- `/api/accounts`
- `/api/accounts/{account_id}`
- `/api/audit`
- `/api/audit/logs`
- `/api/audit/verify`
- `/api/auth/boot`
- `/api/auth/change-password`
- `/api/auth/login`
- `/api/auth/login-json`
- `/api/auth/logout`
- `/api/auth/me`
- `/api/auth/refresh`
- `/api/auth/register`
- `/api/auth/status`
- `/api/backup/export`
- `/api/backup/import`
- `/api/bills`
- `/api/budget`
- `/api/budget/cash-flow`
- `/api/budget/cash-flow-13-week`
- `/api/budget/lines`
- `/api/budget/{period}/variance-alerts`
- `/api/budget/{period}/vs-actual`
- `/api/checks`
- `/api/checks/{account_id}`
- `/api/checks/{transaction_id}/void`
- `/api/clients`
- `/api/clients/{client_id}`
- `/api/coa`
- `/api/coa/coa`
- `/api/coa/coa/seed`
- `/api/coa/coa/{account_id}`
- `/api/coa/coa/{account_id}/parent`
- `/api/coa/coa/{account_id}/renumber`
- `/api/coa/seed`
- `/api/dashboard`
- `/api/dashboard/stats`
- `/api/depreciation`
- `/api/depreciation/{asset_id}`
- `/api/export/balance-sheet`
- `/api/export/formats`
- `/api/export/general-ledger`
- `/api/export/profit-loss`
- `/api/export/statement/{statement_id}`
- `/api/export/transactions`
- `/api/export/trial-balance`
- `/api/flags`
- `/api/flags/{flag_id}`
- `/api/flags/{flag_id}/resolve`
- `/api/fx`
- `/api/fx/convert`
- `/api/fx/rates`
- `/api/fx/report`
- `/api/fx/transactions/{transaction_id}/foreign`
- `/api/fx/transactions/{transaction_id}/settle`
- `/api/health`
- `/api/health/bootstrap`
- `/api/health/config`
- `/api/health/echo-auth`
- `/api/health/migrations`
- `/api/health/public`
- `/api/imports/detect`
- `/api/imports/ofx`
- `/api/inventory`
- `/api/inventory/tags`
- `/api/inventory/tags/search`
- `/api/inventory/tags/{transaction_id}`
- `/api/inventory/{item_id}`
- `/api/inventory/{item_id}/adjust`
- `/api/inventory/{item_id}/transactions`
- `/api/inventory/{item_id}/valuation`
- `/api/investments`
- `/api/investments/lots`
- `/api/investments/prices`
- `/api/investments/{account_id}/cost-basis`
- `/api/investments/{account_id}/dividend`
- `/api/investments/{account_id}/events`
- `/api/investments/{account_id}/holdings`
- `/api/investments/{account_id}/sell`
- `/api/investments/{account_id}/split`
- `/api/investments/{account_id}/unrealized`
- `/api/invoices`
- `/api/invoicing`
- `/api/invoicing/aging`
- `/api/invoicing/bills`
- `/api/invoicing/invoices`
- `/api/invoicing/{invoice_id}`
- `/api/invoicing/{invoice_id}/payments`
- `/api/invoicing/{invoice_id}/payments/{payment_id}`
- `/api/invoicing/{invoice_id}/void`
- `/api/ledger/accounts`
- `/api/ledger/adjusting-entry`
- `/api/ledger/auto-post-batch`
- `/api/ledger/entries`
- `/api/ledger/entries/{entry_id}/workpaper-ref`
- `/api/liabilities`
- `/api/liabilities/amortization`
- `/api/liabilities/credit-lines`
- `/api/liabilities/credit-lines/{cl_id}`
- `/api/liabilities/credit-lines/{cl_id}/available`
- `/api/liabilities/credit-lines/{cl_id}/draw`
- `/api/liabilities/credit-lines/{cl_id}/payment`
- `/api/liabilities/loan-schedule`
- `/api/liabilities/loan-schedule/{schedule_id}`
- `/api/liabilities/loan-schedule/{schedule_id}/payments`
- `/api/liabilities/loan-schedule/{schedule_id}/upcoming`
- `/api/mileage/logs`
- `/api/mileage/summary`
- `/api/ml/categorize/{statement_id}`
- `/api/ml/model-info`
- `/api/ml/status`
- `/api/ml/toggle`
- `/api/ml/train`
- `/api/payments`
- `/api/periods/{period_id}/close`
- `/api/periods/{period_id}/reopen`
- `/api/periods/{period_id}/status`
- `/api/profiles`
- `/api/profiles/{profile_id}`
- `/api/profiles/{profile_id}/members`
- `/api/profiles/{profile_id}/members/{user_id}`
- `/api/reconciliation`
- `/api/reconciliation/import`
- `/api/reconciliation/{import_id}/auto-match`
- `/api/reconciliation/{import_id}/complete`
- `/api/reconciliation/{import_id}/manual-match`
- `/api/reconciliation/{import_id}/matches`
- `/api/reconciliation/{import_id}/reopen`
- `/api/reconciliation/{import_id}/status`
- `/api/reconciliation/{import_id}/unmatch`
- `/api/reconciliation/{import_id}/unmatched`
- `/api/recurring`
- `/api/recurring/{rule_id}`
- `/api/recurring/{rule_id}/materialize`
- `/api/reports`
- `/api/reports/balance-sheet`
- `/api/reports/balance_sheet`
- `/api/reports/cash-flow`
- `/api/reports/cash_flow`
- `/api/reports/pnl`
- `/api/reports/profit-and-loss`
- `/api/reports/trial-balance`
- `/api/reports/trial_balance`
- `/api/rules`
- `/api/rules/{rule_id}`
- `/api/sales-tax/liability-summary`
- `/api/sales-tax/payments`
- `/api/sales-tax/rates`
- `/api/tax`
- `/api/tax-exports/1099`
- `/api/tax-exports/form-1065`
- `/api/tax-exports/form-1120s`
- `/api/tax-exports/form-4562`
- `/api/tax-exports/form-8825`
- `/api/tax-exports/lines`
- `/api/tax-exports/mappings`
- `/api/tax-exports/mappings/{mapping_id}`
- `/api/tax-exports/schedule-c`
- `/api/tax-exports/schedule-e`
- `/api/tax-exports/year-end-package`
- `/api/tax-exports/year-end-summary`
- `/api/tax/summary/{year}`
- `/api/tax/{rule_id}`
- `/api/transactions`
- `/api/transactions/{transaction_id}`
- `/api/transactions/{transaction_id}/running-balance`
- `/api/transactions/{transaction_id}/workpaper-ref`
- `/api/upload`
- `/api/vendors`
- `/api/vendors/{vendor_id}`
- `/api/year-end/close`