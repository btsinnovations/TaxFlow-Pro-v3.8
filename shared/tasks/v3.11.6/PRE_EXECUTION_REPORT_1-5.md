# TaxFlow Pro v3.11.6 — Pre-Execution Report (Steps 1–5)

**Date:** 2026-06-27  
**Orchestrator:** James Clawd  
**Branch:** `v3.11.6-dev` (cut from `v3.11.5` tag at `eeb1001`, roadmap cherry-picked to `1284342`)  
**Baseline:** `v3.11.5-dev` reset to `eeb1001` and frozen.

---

## Step 1 — Audit Current Codebase for Hidden Scaffolding

### Backend accounting modules exist and are substantial
Most v3.11 modules already have real backend code, not just stubs:

| Module | File | Lines | Functions/Classes | Test File | Test Functions |
|--------|------|-------|-------------------|-----------|----------------|
| Recurring | `backend/accounting/recurring.py` | 402 | 12 | `test_recurring.py` | 17 |
| COA | `backend/accounting/coa.py` | 299 | 9 | `test_coa.py` | 13 |
| Register | `backend/accounting/register.py` | 225 | 6 | `test_register.py` | 6 |
| Invoicing | `backend/accounting/invoicing.py` | 171 | 7 | `test_invoicing.py` | 11 |
| Reconciliation | `backend/accounting/reconciliation.py` | 132 | 4 | `test_reconciliation.py` | 8 |
| Liabilities | `backend/accounting/liabilities.py` | 119 | 4 | `test_liabilities.py` | 10 |
| Investments | `backend/accounting/investments.py` | 111 | 4 | `test_investments.py` | 9 |
| Budget | `backend/accounting/budget.py` | 116 | 3 | `test_budget.py` | 7 |
| Tax Exports | `backend/accounting/tax_exports.py` | 103 | 3 | `test_tax_exports.py` | 8 |
| Checks | `backend/accounting/checks.py` | 99 | 4 | `test_checks.py` | 12 |
| Inventory | `backend/accounting/inventory.py` | 94 | 4 | `test_inventory.py` | 9 |
| FX | `backend/accounting/fx.py` | 89 | 4 | `test_fx.py` | 8 |
| Reports | `backend/accounting/reports.py` | 76 | 2 | `test_reports.py` | 6 |

### Backend routers already wired in `backend/api.py`
All 13 module routers plus the existing infrastructure routers are already included:
- `coa`, `profiles` (roles), `transactions` (register), `recurring`, `checks`, `inventory`, `fx`, `reconciliation`, `reports`, `budget`, `invoicing`, `liabilities`, `investments`

### Models already have v3.11 tables
`backend/models.py` already defines:
- `ProfileMembership`
- `LoanSchedule`
- `InvestmentLot`
- `InventoryItem`
- `InventoryTransaction`
- `FXRate`
- `ReconciliationImport`
- `ReconciliationMatch`
- `BudgetLine`
- `TaxLineMapping`
- `RecurringRule`

### Frontend v3.11 shells exist but some are thin
- `frontend/src/components/v3.11/` contains components for all major modules.
- Functional-looking: `BankReconciliation.tsx`, `BudgetForecast.tsx`, `CheckRegister.tsx`, `InvoicingAPAR.tsx`, `LiabilitiesInvestments.tsx`, `MultiCurrency.tsx`, `ReportsCenter.tsx`, `TaxFilingExports.tsx`.
- Some `.test.tsx` files are ~19-line skeletons that need real tests.

### Verdict on scaffolding
The v3.11 backend is far more real than expected. The work for v3.11.6 is likely:
- Hardening and completing the existing modules
- Adding missing integration points
- Filling empty/skeleton frontend tests
- Wiring the frontend to actually use the backend endpoints
- PostgreSQL RLS
- Packaging/hardening

Not a greenfield build.

---

## Step 2 — Lock the Baseline

- `v3.11.5` tag: `eeb1001`
- `v3.11.5-dev`: reset to `eeb1001` and frozen. No more v3.11.5 work allowed.
- `v3.11.6-dev`: cut from `v3.11.5` tag, roadmap/scaffold cherry-picked to `1284342`.
- `v3.11.6-dev` pushed to origin and tracking.

---

## Step 3 — Resolve Open Architectural Decisions

### Confirmed
1. **Tenant = Client** boundary holds for v3.11.6 (from `shared/decisions/v3.11.5-rls-tenant-boundary.md` and existing `tenant_id` columns).
2. **SQLite remains default offline DB.** PostgreSQL is optional production. RLS on SQLite is application-level; PostgreSQL gets native RLS.
3. **COA migration strategy:** existing `GLAccount` table is reused conceptually as `coa_accounts`. Data preservation path exists but needs validation in v3.11.6.

### Decisions confirmed by Josh 2026-06-27
1. **Replace `accounts` table with COA** — `accounts` becomes the bank/credit-card view of COA, not a separate entity.
2. **True COA renumbering migration** — migrate `GLAccount` into a proper `coa_accounts` table with hierarchy.
3. **Multi-currency conversion required in reports** — home-currency conversion must work in registers and reports.
4. **macOS host** — **defer** to v3.11.7.
5. **Code signing / trust signals** — **document only** for v3.11.6.

### Still needs orchestrator detail — RESOLVED
- **Default small-business COA numbering scheme:**  
  - Assets: 1000–1999  
  - Liabilities: 2000–2999  
  - Equity: 3000–3999  
  - Income/Revenue: 4000–4999  
  - Expenses: 5000–9999  
- **Old `Account` records:** **DROP**. Migration does not preserve legacy `Account` rows; users must re-add bank/credit card accounts as COA entries.
- **Default home currency:** **USD**.

---

## Step 4 — Secure Infrastructure Before Delegation

| Resource | Status | Blocker |
|----------|--------|---------|
| PostgreSQL for RLS testing | Not yet provisioned | Need Docker or live Postgres instance |
| macOS host for packaging | Not available | Decision pending |
| CI runner capacity | Current suite ~5 min focused, ~4 min full | Will grow significantly with frontend e2e; monitor |
| Frontend e2e runner | None configured | Need decision: Playwright, Cypress, or build + component smoke only |

Recommended immediate actions:
- Provision local PostgreSQL via Docker for RLS validation.
- Decide macOS host availability before scheduling B7.

---

## Step 5 — Define Frontend/Backend Contracts (Draft)

The existing API surface already has most endpoints. Before parallel subagents run, we need a canonical contract doc to prevent drift. Proposed contract areas to document:

1. **COA endpoints** — `/api/coa/...` shapes
2. **Register endpoints** — `/api/transactions/...` list filters, pagination, splits
3. **Recurring endpoints** — `/api/recurring/...` rule + occurrence model
4. **Inventory endpoints** — `/api/inventory/...` item + transaction model
5. **FX endpoints** — `/api/fx/...` rate + conversion model
6. **Reports endpoints** — `/api/reports/...` report request + response
7. **Reconciliation endpoints** — `/api/reconciliation/...` import + match model
8. **Tax exports endpoints** — `/api/tax-exports/...`
9. **Budget endpoints** — `/api/budget/...`
10. **Invoicing endpoints** — `/api/invoices/...`, `/api/bills/...`, `/api/payments/...`

This contract doc should be created as the first deliverable of B1 before any other bundle starts.

---

## Test Health Snapshot

Focused run of v3.11 area tests:
- **147 passed, 56 warnings in 69.65s**
- 0 failures across COA, register, recurring, checks, liabilities, investments, inventory, FX, reconciliation, tax exports, reports, budget, invoicing, roles, RLS SQLite, and alembic migrations.

This confirms the existing v3.11 backend modules are already functional enough to build on.

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Existing modules are "real" but may have edge-case gaps | Medium | GLM validation per bundle |
| Frontend shells may not actually call backend correctly | High | End-to-end register smoke test as first B6 milestone |
| PostgreSQL RLS complexity | Medium | Provision Postgres early; test in CI |
| macOS host unavailable | Medium | Defer to v3.11.7 if no host by week 5 |
| Migration from v3.10/v3.11.5 data | High | Round-trip migration tests; backup import wizard |
| Scope creep (13 modules + hardening) | High | Strict bundle gating; cut features if slipping |

---

## Recommended Next Actions (after this report)

1. Create the API contract doc as part of B1 kickoff.
2. Provision PostgreSQL test instance.
3. Decide the 5 open architectural questions above.
4. Spawn B1 subagent with a focused brief: "complete COA/roles/migration/RLS contract and implementation, no other bundles touched."
5. Postpone frontend-heavy B6 until B1 and at least B2 deliver real endpoints.

---

*Report prepared by James Clawd (orchestrator) as pre-execution due diligence for TaxFlow Pro v3.11.6.*
