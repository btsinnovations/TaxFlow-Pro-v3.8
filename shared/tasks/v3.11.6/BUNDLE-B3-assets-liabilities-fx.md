# Bundle B3 — Assets, Liabilities & FX

**Goal:** Track loans, investments, inventory, project tags, and multi-currency transactions.

---

## 3.11.6.B3.01 — Loans / Credit Lines Backend

### Files
- `backend/accounting/liabilities.py`
- `backend/routers/liabilities.py`
- `backend/tests/test_liabilities.py`

### Requirements
- `loan_schedules` table: account_id, schedule_type, original_principal, rate, term, start_date.
- Amortization schedules: fixed principal + interest breakdown per period.
- Credit line: available credit, current balance, interest accrual (simple).
- Endpoint to generate upcoming payment transactions.
- Track payment allocation to principal/interest.

### Tests
- Create amortized loan.
- Generate 12-month schedule.
- Record payment and verify principal/interest split.
- Credit line draw/payment.
- Tenant isolation.

---

## 3.11.6.B3.02 — Investments Backend

### Files
- `backend/accounting/investments.py`
- `backend/routers/investments.py`
- `backend/tests/test_investments.py`

### Requirements
- `investment_lots` table: account_id, shares, cost_basis, acquisition_date.
- Track realized/unrealized gains (FIFO lot selection).
- Support buy, sell, dividend, split events.
- Cost-basis reporting for tax exports.
- Simple price snapshots (manual entry; no live API).

### Tests
- Record buy lot.
- Sell shares with FIFO cost basis.
- Dividend event.
- Unrealized gain calculation.
- Tenant isolation.

---

## 3.11.6.B3.03 — Inventory & Project Tags Backend

### Files
- `backend/accounting/inventory.py`
- `backend/routers/inventory.py`
- `backend/tests/test_inventory.py`

### Requirements
- `inventory_items` table: sku, name, cogs_account_id, income_account_id, valuation_method, qty_on_hand.
- `inventory_transactions` table: item_id, qty, unit_cost, valuation_method snapshot.
- Valuation methods: FIFO, average cost (LIFO out of scope).
- Project tags: free-form labels attached to transactions.
- Transaction tag search/filtering.

### Tests
- Create item.
- Receive inventory increases qty/average cost.
- Sell inventory reduces qty and records COGS.
- Tag transactions and filter by tag.
- Tenant isolation.

---

## 3.11.6.B3.04 — Multi-Currency Backend

### Files
- `backend/accounting/fx.py`
- `backend/routers/fx.py`
- `backend/tests/test_fx.py`

### Requirements
- `fx_rates` table: from_currency, to_currency, rate, effective_date.
- Manual rate entry (no live FX API).
- Transactions can record `foreign_amount` + `foreign_currency` + home-currency equivalent.
- Convert transaction amounts at transaction date rate or most recent rate.
- Reporting in home currency with FX gain/loss.

### Tests
- Add FX rate.
- Create foreign-currency transaction.
- Convert to home currency.
- FX gain/loss on payment.
- Tenant isolation.
