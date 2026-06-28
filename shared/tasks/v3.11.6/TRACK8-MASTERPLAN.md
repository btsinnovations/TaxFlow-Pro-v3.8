# TaxFlow Pro v3.11.6 — Track 8 Masterplan (B6 Frontend UI Shell)

**Branch:** `v3.11.6-dev-PHASE4-TRACK8-frontend-ui-shell`  
**Cut from:** `v3.11.6-dev` (HEAD `675af7c`)  
**Goal:** Build the frontend UI shell that consumes the B1–B5 backend APIs, making the bookkeeping platform usable end-to-end.

---

## Why Track 8 Exists

B1–B5 delivered the backend data model, transaction engine, asset/liability/FX tracking, financial operations, and invoicing. Track 8 builds the user-facing components: unified register, chart of accounts tree, reports center, reconciliation UI, tax exports, inventory center, and profile roles management.

---

## Modules & Acceptance Criteria

### B6.01 — TanStack Table + Register Scaffolding

**Files to create/update:**
- `frontend/src/components/ui/data-table.tsx`
- `frontend/src/hooks/useTransactions.ts`
- `frontend/src/types/register.ts`

**Requirements:**
- Reusable TanStack Table wrapper with sorting, filtering, pagination
- Virtual scrolling for large datasets
- Type-safe row actions
- Theme-compatible styling with shadcn/ui

**Acceptance:**
- Component renders
- Sort toggle works
- Filter input narrows rows
- Pagination changes page

---

### B6.02 — Unified Register Component

**Files:**
- `frontend/src/components/register/Register.tsx`
- `frontend/src/components/register/RegisterRow.tsx`
- `frontend/src/components/register/SplitEditor.tsx`

**Requirements:**
- Display transactions in register grid
- Inline edit of date, payee, amount, account, description, tags
- Add split lines inline
- Bulk select + delete
- Reconciled status toggle
- Search/filter bar

**Acceptance:**
- List transactions
- Edit transaction inline
- Add split
- Delete transaction
- Filter by date/account

---

### B6.03 — Chart of Accounts Tree Component

**Files:**
- `frontend/src/components/accounts/COATree.tsx`
- `frontend/src/components/accounts/AccountForm.tsx`

**Requirements:**
- Hierarchical tree view of COA
- Add/edit/delete accounts
- Show account balance if available
- Drag-and-drop / renumbering optional for v3.11.6 (stretch)

**Acceptance:**
- Render tree
- Add account
- Edit account
- Delete inactive account

---

### B6.04 — Reports Center Component

**Files:**
- `frontend/src/components/reports/Reports.tsx`
- `frontend/src/components/reports/ReportCard.tsx`

**Requirements:**
- Report picker: P&L, Balance Sheet, Cash Flow, Trial Balance, GL Detail
- Date-range selector
- Export buttons (CSV)
- Recharts charts for P&L and cash flow

**Acceptance:**
- Select report
- Render chart
- Export triggers download

---

### B6.05 — Reconciliation Component

**Files:**
- `frontend/src/components/reconciliation/Reconciliation.tsx`
- `frontend/src/components/reconciliation/MatchList.tsx`

**Requirements:**
- Select account and statement period
- Import statement rows
- Show auto-matched vs unmatched
- Manual match/unmatch UI
- Mark reconciled

**Acceptance:**
- Import statement rows
- Accept auto-matches
- Manually match
- Mark reconciled

---

### B6.06 — Tax Export Component

**Files:**
- `frontend/src/components/tax/TaxExports.tsx`

**Requirements:**
- Choose export scope and date range
- Map categories to tax lines
- Preview export
- Download export package

**Acceptance:**
- Select scope
- Map category
- Download export

---

### B6.07 — Inventory Component

**Files:**
- `frontend/src/components/inventory/InventoryCenter.tsx`
- `frontend/src/components/inventory/InventoryItemForm.tsx`

**Requirements:**
- List inventory items with qty/value
- Add/edit items
- View transaction history for item
- Project tag editor

**Acceptance:**
- List items
- Add item
- Edit item
- Filter by tag

---

### B6.08 — Profile Roles UI

**Files:**
- `frontend/src/components/accounts/RoleManager.tsx`

**Requirements:**
- List profile members
- Change role
- Remove member
- In single-user offline mode, show current user as owner and disable editing

**Acceptance:**
- Render roles
- Change role
- Remove member

---

## Technical Notes

- Backend API base URL is already configured in the frontend.
- Use existing frontend conventions: Vite + React + shadcn/ui + TanStack Query (if used) or fetch hooks.
- TypeScript strictly required.
- Vitest for unit tests; Storybook not required unless already configured.
- Keep components route-ready but do not wire all routing if it adds scope.
- Single-user offline mode (`TAXFLOW_SINGLE_USER=true`) should hide multi-entity features gracefully.

---

## Definition of Done

- All 8 B6 modules scaffolded and functional
- `npm run build` passes (`tsc -b && vite build`)
- `npm run test` passes
- `npm run lint` passes
- Branch pushed to origin
- No merge to `v3.11.6-dev` without James approval
- API contract updated only if backend endpoint shapes need adjustment

---

## Suggested Execution Order

1. TanStack Table scaffolding
2. Unified Register (highest user value)
3. COA Tree
4. Reports Center
5. Reconciliation
6. Tax Export
7. Inventory
8. Profile Roles

---

## Assignment

- **Primary builder:** Jane Clawd
- **Validator:** glm-5.2:cloud for final build + lint + test pass review
- **Orchestrator approval:** James before merge
