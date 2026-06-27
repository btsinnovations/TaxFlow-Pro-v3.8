# Bundle B6 — Frontend UI Shell

**Goal:** Deliver the unified register component and module UIs so the bookkeeping backend is usable end-to-end.

---

## 3.11.6.B6.01 — TanStack Table + Register Scaffolding

### Files
- `frontend/src/components/ui/data-table.tsx`
- `frontend/src/hooks/useTransactions.ts`
- `frontend/src/types/register.ts`

### Requirements
- Reusable TanStack Table wrapper with sorting, filtering, pagination.
- Virtual scrolling for large datasets.
- Type-safe row actions.
- Theme-compatible styling with shadcn/ui.

### Tests
- Component renders.
- Sort toggle works.
- Filter input narrows rows.
- Pagination changes page.

---

## 3.11.6.B6.02 — Unified Register Component

### Files
- `frontend/src/components/register/Register.tsx`
- `frontend/src/components/register/RegisterRow.tsx`
- `frontend/src/components/register/SplitEditor.tsx`

### Requirements
- Display transactions in register grid.
- Inline edit of date, payee, amount, account, description, tags.
- Add split lines inline.
- Bulk select + delete.
- Reconciled status toggle.
- Search/filter bar.

### Tests
- List transactions.
- Edit transaction inline.
- Add split.
- Delete transaction.
- Filter by date/account.

---

## 3.11.6.B6.03 — Chart of Accounts Tree Component

### Files
- `frontend/src/components/accounts/COATree.tsx`
- `frontend/src/components/accounts/AccountForm.tsx`

### Requirements
- Hierarchical tree view of COA.
- Add/edit/delete accounts.
- Drag-and-drop optional; renumbering supported.
- Show account balance if available.

### Tests
- Render tree.
- Add account.
- Edit account.
- Delete inactive account.

---

## 3.11.6.B6.04 — Reports Center Component

### Files
- `frontend/src/components/reports/Reports.tsx`
- `frontend/src/components/reports/ReportCard.tsx`

### Requirements
- Report picker: P&L, Balance Sheet, Cash Flow, Trial Balance, GL Detail.
- Date-range selector.
- Export buttons (CSV/Excel/PDF).
- Recharts charts for P&L and cash flow.

### Tests
- Select report.
- Render chart.
- Export triggers download.

---

## 3.11.6.B6.05 — Reconciliation Component

### Files
- `frontend/src/components/reconciliation/Reconciliation.tsx`
- `frontend/src/components/reconciliation/MatchList.tsx`

### Requirements
- Select account and statement period.
- Upload/import statement.
- Show auto-matched vs unmatched.
- Manual match/unmatch UI.
- Mark reconciled.

### Tests
- Import statement.
- Accept auto-matches.
- Manually match.
- Mark reconciled.

---

## 3.11.6.B6.06 — Tax Export Component

### Files
- `frontend/src/components/tax/TaxExports.tsx`

### Requirements
- Choose export scope and date range.
- Map categories to tax lines.
- Preview export.
- Download signed export package.

### Tests
- Select scope.
- Map category.
- Download export.

---

## 3.11.6.B6.07 — Inventory Component

### Files
- `frontend/src/components/inventory/InventoryCenter.tsx`
- `frontend/src/components/inventory/InventoryItemForm.tsx`

### Requirements
- List inventory items with qty/value.
- Add/edit items.
- View transaction history for item.
- Project tag editor.

### Tests
- List items.
- Add item.
- Edit item.
- Filter by tag.

---

## 3.11.6.B6.08 — Profile Roles UI

### Files
- `frontend/src/components/accounts/RoleManager.tsx`

### Requirements
- List profile members.
- Change role.
- Remove member.
- In single-user offline mode, show current user as owner and disable editing.

### Tests
- Render roles.
- Change role.
- Remove member.
