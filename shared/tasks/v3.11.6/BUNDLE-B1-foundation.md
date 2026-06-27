# Bundle B1 — Foundation & Data Model

**Goal:** Establish the v3.11.6 data model, tenant boundary, and core accounting primitives so later bundles build on a solid base.

---

## 3.11.6.B1.01 — Chart of Accounts Backend

### Files
- `backend/accounting/coa.py`
- `backend/routers/coa.py`
- `backend/tests/test_coa.py`

### Requirements
- Hierarchical COA: accounts have `number`, `name`, `type`, `parent_id`, `is_active`.
- Account types: Asset, Liability, Equity, Revenue, Expense.
- CRUD endpoints under `/api/coa/` with tenant scoping.
- Seed a standard small-business COA for new profiles.
- Prevent deletion of accounts with transactions.
- Support account renumbering and parent reassignment.

### Tests
- Create root account.
- Create child account.
- Seed default COA.
- Delete account with no activity.
- Fail to delete account with transactions.
- Tenant isolation: user A cannot see user B's COA.

---

## 3.11.6.B1.02 — Profile Roles & Memberships Backend

### Files
- `backend/local/roles.py`
- `backend/routers/profiles.py`
- `backend/tests/test_roles.py`

### Requirements
- Roles: owner, admin, bookkeeper, viewer.
- `profile_memberships` table: `user_id`, `profile_id`, `role`, `created_at`.
- Single-user offline mode defaults current user to owner.
- Role checks on sensitive routers (COA, exports, reconciliation).
- Invitation flow is out of scope; membership assignment via admin UI.

### Tests
- Default single-user owner.
- Viewer cannot create accounts.
- Bookkeeper cannot delete COA.
- Admin can assign roles.

---

## 3.11.6.B1.03 — PostgreSQL Native RLS Policies

### Files
- `backend/rls.py`
- `backend/database.py`
- `backend/tests/test_rls_postgres.py`
- Alembic migration for policy functions

### Requirements
- When `DATABASE_URL` points to PostgreSQL, enable RLS on:
  - `clients`, `accounts`, `statements`, `transactions`, `audit_entries`, `journals`, `periods`, `categorization_rules`, `general_ledger_entries`, `flags`, `gl_accounts`, `recurring_rules`, `trained_models`.
- Use `app.current_tenant_id()` or equivalent session variable.
- Provide a service-role bypass for migrations and admin operations.
- Keep SQLite path as no-op (application-level scoping already in place).

### Tests
- Run against live PostgreSQL instance.
- Cross-tenant read rejected at DB level.
- Cross-tenant write rejected at DB level.
- Service role can bypass for migrations.

---

## 3.11.6.B1.04 — Alembic Migration to v3.11.6 Schema

### Files
- `alembic/versions/` new migration
- `backend/accounting/models.py` (or extend existing models)

### Requirements
- Replace legacy `accounts`/`gl_accounts` with `coa_accounts` while preserving data.
- Add `profile_memberships`, `recurring_rules`, `inventory_items`, `inventory_transactions`, `fx_rates`, `loan_schedules`, `investment_lots`, `reconciliation_imports`, `reconciliation_matches`, `budget_lines`.
- Update `transactions` to support `splits JSON`, `foreign_amount`, `foreign_currency`, `project_tags`.
- Migration must be reversible.

### Tests
- Upgrade from v3.11.5 baseline.
- Downgrade back to v3.11.5 baseline.
- Data preserved across round-trip.
