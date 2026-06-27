# TaxFlow Pro v3.11.6 — Phase 1 Masterplan

**Phase goal:** Establish the test substrate and the v3.11.6 data foundation.  
**Branch:** `v3.11.6-dev`  
**Builder / Persistent Agent:** Jane Clawd  
**Orchestrator:** James Clawd  
**Validator:** glm-5.1 subagent (spawned by Jane as needed)

---

## Context Jane Must Read First

Before doing any work, read these files in order:

1. `shared/tasks/v3.11.6/V3.11.6-ROADMAP.md` — release bundles and phasing
2. `shared/tasks/v3.11.6/SUBAGENT_PROTOCOL.md` — branch rules, commit rules, merge gates
3. `shared/tasks/v3.11.6/TEST_HARNESS.md` — test harness plan
4. `shared/tasks/v3.11.6/BUNDLE-B1-foundation.md` — detailed B1 requirements
5. `shared/tasks/v3.11.6/PRE_EXECUTION_REPORT_1-5.md` — audit findings and locked decisions

All architectural decisions are already made:
- Tenant = Client
- Replace `Account` table with COA; drop legacy `Account` records
- True COA renumbering migration from `GLAccount` to `coa_accounts`
- Multi-currency home-currency conversion required in reports
- macOS deferred to v3.11.7
- Code signing document-only
- Default COA numbering:
  - Assets: 1000–1999
  - Liabilities: 2000–2999
  - Equity: 3000–3999
  - Revenue: 4000–4999
  - Expenses: 5000–9999
- Default home currency: USD

---

## Phase 1 Tracks

Phase 1 has **two tracks**. Track 1 must complete before Track 2 starts.

| Track | ID | Goal | Owner | Output |
|-------|----|------|-------|--------|
| 1 | `PHASE1-TRACK1` | Test harness | Jane | Fixtures, MSW, CI job |
| 2 | `PHASE1-TRACK2` | B1 Foundation | Jane | COA, roles, migration, RLS, API contract |

---

## Track 1 — Test Harness

### Task
Build the testing substrate that all later bundles will use.

### Deliverables
1. **Frontend MSW setup**
   - Add `msw` to `frontend/package.json` devDependencies.
   - Create `frontend/src/mocks/handlers.ts` with mock handlers for all v3.11 API paths:
     - `/api/coa/*`
     - `/api/transactions/*`
     - `/api/recurring/*`
     - `/api/checks/*`
     - `/api/inventory/*`
     - `/api/fx/*`
     - `/api/reconciliation/*`
     - `/api/reports/*`
     - `/api/budget/*`
     - `/api/invoices/*`, `/api/bills/*`, `/api/payments/*`
     - `/api/liabilities/*`
     - `/api/investments/*`
   - Create `frontend/src/mocks/server.ts` and `frontend/src/mocks/browser.ts`.
   - Wire MSW into `frontend/src/main.tsx` for dev/tests.
   - Update at least one existing `v3.11/*.test.tsx` skeleton to use MSW.

2. **Backend test fixtures**
   - Add `tenant` fixture to `backend/tests/conftest.py` that returns a seeded client/tenant.
   - Add `viewer_member` fixture that returns a second user with `viewer` role in the tenant.
   - Add `admin_member` fixture.
   - Add helper `switch_profile(client, profile_id)` for multi-tenant tests.

3. **PostgreSQL test fixture**
   - Add optional `postgres_client` fixture that reads `TEST_DATABASE_URL`.
   - Fixture must create schema, run migrations, and drop/recreate after test class.
   - Guard so tests skip gracefully when `TEST_DATABASE_URL` is not set.

4. **CI workflow update**
   - Update `.github/workflows/ci.yml` to include:
     - Frontend build + Vitest job
     - PostgreSQL service container for backend tests
     - Job conditional to run `test_rls_postgres.py` when Postgres is available

### Acceptance Criteria
- `cd frontend && npm install && npm run build` passes with 0 TypeScript errors.
- `cd frontend && npm run test` passes with the MSW-updated test.
- `python -m pytest backend/tests/test_rls_postgres.py -q` runs without crashing when `TEST_DATABASE_URL` is set (may skip if not set).
- New fixtures are used by at least one existing backend test.

### Work Branch
`v3.11.6-dev-PHASE1-TRACK1-test-harness`

### Subagent Option
Jane may do this herself or spawn a specialist subagent. If spawning, include:
- This file path
- `TEST_HARNESS.md`
- Branch and acceptance criteria above
- Constraint: do not touch any B1–B7 logic

---

## Track 2 — B1 Foundation

### Task
Implement the data model, tenant boundary, and core accounting primitives.

### Deliverables
1. **Alembic migration: v3.11.5 → v3.11.6**
   - Create new `coa_accounts` table:
     - `id`, `tenant_id`, `parent_id`, `number`, `name`, `type`, `is_active`, `created_at`, `updated_at`
   - Drop legacy `Account` table and any FK references.
   - Preserve existing `GLAccount` rows by migrating them into `coa_accounts` where possible; otherwise drop them per Josh decision.
   - Ensure `Statement`, `Transaction`, and other tables that referenced `accounts.id` now reference `coa_accounts.id` where appropriate.
   - Add missing v3.11 tables if not already present:
     - `profile_memberships` (already exists, verify columns)
     - `loan_schedules`, `investment_lots`, `inventory_items`, `inventory_transactions`, `fx_rates`, `reconciliation_imports`, `reconciliation_matches`, `budget_lines`, `recurring_rules`, `tax_line_mappings`
   - Migration must be reversible.

2. **COA backend (`backend/accounting/coa.py`, `backend/routers/coa.py`)**
   - Hierarchical CRUD with tenant scoping.
   - Seed standard small-business COA using the locked numbering scheme.
   - Prevent deletion of accounts with transactions.
   - Support renumbering and parent reassignment.

3. **Profile roles & memberships (`backend/local/roles.py`, `backend/routers/profiles.py`)**
   - Roles: owner, admin, bookkeeper, viewer.
   - Enforce role checks on sensitive routers.
   - Single-user offline mode defaults current user to owner.

4. **PostgreSQL native RLS**
   - Add policies to all core tables when `DATABASE_URL` points to PostgreSQL.
   - Use `app.current_tenant_id()` or session variable approach consistent with existing `backend/rls.py`.
   - Provide service-role bypass for migrations.

5. **API contract doc**
   - Create `shared/tasks/v3.11.6/API-CONTRACT.md` with canonical request/response shapes for all v3.11 endpoints.
   - This doc is the contract between backend and frontend teams.

### Acceptance Criteria
- `python -m pytest backend/tests/test_coa.py backend/tests/test_roles.py backend/tests/test_alembic_migrations.py backend/tests/test_rls_sqlite.py -q` passes.
- `python -m pytest backend/tests/test_rls_postgres.py -q` passes when `TEST_DATABASE_URL` is set.
- `cd frontend && npm run build` passes.
- Full suite `python -m pytest backend/tests tests -q` still passes (target: 0 failures).
- `API-CONTRACT.md` reviewed and approved by James.

### Work Branch
`v3.11.6-dev-PHASE1-TRACK2-B1-foundation`

### Subagent Option
Jane may do this herself or spawn a specialist subagent. If spawning, include:
- This file path
- `BUNDLE-B1-foundation.md`
- Branch and acceptance criteria above
- Constraint: must use Track 1 fixtures and test harness

---

## Execution Order

1. Jane reads all required context files.
2. Jane executes **Track 1** (test harness) herself or via subagent.
3. Jane validates Track 1 against acceptance criteria.
4. Jane reports Track 1 completion to James.
5. James approves Track 1 merge to `v3.11.6-dev`.
6. Jane executes **Track 2** (B1 Foundation) herself or via subagent.
7. Jane validates Track 2 against acceptance criteria.
8. Jane reports Track 2 completion to James.
9. James approves Track 2 merge to `v3.11.6-dev`.
10. Phase 1 complete.

---

## Blocker Escalation Format

If Jane hits a blocker, report to James as:

```
PHASE 1 BLOCKER — Track X
Summary: one-line description
Impact: what is stuck
Options:
  A) option A
  B) option B
  C) option C
Recommendation: A/B/C
```

Do not change scope or pivot without James approval.

---

## Notes

- Track 1 and Track 2 are sequential to avoid fixture/test chaos in B1.
- Jane is the persistent builder; she owns both tracks and may spawn subagents for focused work.
- No merge to `v3.11.6-dev` without James approval.
- macOS packaging and code signing are out of scope for Phase 1.
