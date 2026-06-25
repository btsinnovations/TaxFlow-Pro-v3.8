# TASK-3.11.FE — Frontend Scaffolding

**Owner:** Jane  
**Goal:** Set up TanStack Table v8 register scaffolding and build missing module UI components.

## Current State

- Existing components: `COATree.tsx`, `RoleManager.tsx`, `Register.tsx`, `RecurringRules.tsx`.
- Missing: reports, reconciliation, tax exports, inventory, budget, invoicing, OFX upload, tax rules search, export polish.
- `App.tsx` updated with v3.11 component index.

## Files

- `frontend/src/components/v3.11/index.ts` — export all v3.11 components.
- Add individual components as listed in `V3.11-TASKS-UPDATED.md`.
- Update `frontend/src/App.tsx` navigation: Dashboard → Upload → Processed Files.

## Components to Build

- `Register.tsx` — TanStack Table, columns: date, account, description, debit, credit, balance, category, actions.
- `COATree.tsx` — tree view of COA accounts with add/edit/delete.
- `Reconciliation.tsx` — statement import + auto-match + status.
- `TaxExports.tsx` — Schedule C preview + mappings.
- `Reports.tsx` — P&L and trial balance.
- `Budget.tsx` — budget vs actual + cash flow forecast.
- `InventoryCenter.tsx` — inventory items + adjustments + project tags.
- `Invoicing.tsx` — invoices/bills + payments + aging.
- `FXRates.tsx` — FX rate management + converter.
- `TaxRulesSearch.tsx` — search/filter UI for categorization rules.
- `OFXUpload.tsx` — OFX file upload + account mapping.
- `ExportPanel.tsx` — polished export formats.

## Tests

- Each component has a basic render test.
- Use Vitest / React Testing Library.

## Constraints

- Use shadcn/ui components.
- Offline-first; mock API responses in tests.

## Report

Files changed, test command + result, blockers.
