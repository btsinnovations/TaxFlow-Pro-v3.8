# TASK-3.11.07 — Inventory & Project Tags

**Owner:** Jane  
**Goal:** Complete inventory module: tests, project-tag support, and frontend component.

## Current State

- `backend/accounting/inventory.py` — create item, adjust quantity (purchase/sale/adjustment), list items
- `backend/routers/inventory.py` — endpoints exist
- Models: `InventoryItem`, `InventoryTransaction`
- Tests: **missing**
- Frontend: **missing**

## Files

- `backend/tests/test_inventory.py` — new
- `frontend/src/components/inventory/InventoryCenter.tsx` — new

## Backend Tests Required

1. `test_create_inventory_item`
   - Create item, assert defaults (average cost, qty 0).
2. `test_purchase_updates_average_cost`
   - Purchase 10 @ $5, assert qty 10, unit cost $5.
   - Purchase 10 @ $7, assert qty 20, unit cost $6.
3. `test_sale_reduces_quantity`
   - Purchase then sell 5; qty drops by 5.
4. `test_sale_without_inventory_fails`
   - Sell before purchase raises `InventoryError`.
5. `test_adjustment_overwrites_quantity`
   - Adjustment type sets qty to exact value.
6. `test_list_items_filters_by_user_and_tenant`
   - Only items for current tenant/user returned.

## Project Tags

- The spec mentions project tags on transactions.
- Add `project_tag` column to `Transaction` model (string, nullable) OR use existing `workpaper_ref` / `category` field.
- Recommended: add `project_tag` column and expose in register/transactions endpoints.
- Tests: create transaction with project tag, filter register by tag.

## Frontend

- `InventoryCenter.tsx`: list items, show qty/unit cost, adjust quantity form.
- Add project-tag input to Register/Transaction modal.

## Constraints

- Offline-only.
- Maintain average-cost valuation for purchases.

## Report

Files changed, test command + result, blockers.
