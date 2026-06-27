# TaxFlow Pro v3.11.6 — Test Harness Plan

**Date:** 2026-06-27  
**Goal:** Define how v3.11.6 will be tested end-to-end before any code is written.

---

## 1. Backend Test Harness

### Existing state
- `backend/tests/conftest.py` provides a per-test in-memory SQLite database with schema creation from `Base.metadata`.
- Fixtures: `client`, `db`, `auth_client`, `test_user`.
- Global rate limiter is disabled in tests.
- Single-user offline mode is forced via env vars.

### Required additions for v3.11.6

#### 1.1 PostgreSQL test fixture
Add an optional `postgres_client` fixture that:
- Reads `TEST_DATABASE_URL` env var (defaults to `postgresql://taxflow_test:taxflow_test@localhost:5432/taxflow_test`).
- Creates schema, runs migrations, yields `TestClient`.
- Drops/recreates schema after test class.
- Used only by `test_rls_postgres.py` to validate native RLS.

#### 1.2 Tenant seed helper
Centralize `_seed_tenant_and_user()` across bundle tests into `conftest.py`:
```python
@pytest.fixture
def tenant(db):
    return _create_test_tenant(db, name="Bundle Tenant")
```

#### 1.3 Role fixture
```python
@pytest.fixture
def viewer_member(db, tenant):
    return _create_user_with_role(db, tenant, role="viewer")
```

#### 1.4 Profile switch helper
For multi-profile tests:
```python
def switch_profile(client, profile_id):
    # Sets active tenant via header or session
```

### Test commands
```bash
# Bundle-focused
python -m pytest backend/tests/test_coa.py backend/tests/test_register.py -q

# All v3.11 areas
python -m pytest backend/tests/test_coa.py backend/tests/test_register.py backend/tests/test_recurring.py backend/tests/test_checks.py backend/tests/test_liabilities.py backend/tests/test_investments.py backend/tests/test_inventory.py backend/tests/test_fx.py backend/tests/test_reconciliation.py backend/tests/test_tax_exports.py backend/tests/test_reports.py backend/tests/test_budget.py backend/tests/test_invoicing.py backend/tests/test_roles.py -q

# Full suite
python -m pytest backend/tests tests -q

# RLS on PostgreSQL (requires TEST_DATABASE_URL)
python -m pytest backend/tests/test_rls_postgres.py -q
```

---

## 2. Frontend Test Harness

### Existing state
- Framework: **Vitest** with `jsdom` and `@testing-library/react`.
- Build command: `npm run build` (runs `tsc -b && vite build`).
- Test command: `npm run test`.

### Required additions for v3.11.6

#### 2.1 Component test patterns
Each frontend component should have tests in `frontend/src/components/v3.11/*.test.tsx` that verify:
- Component renders without crashing.
- User interactions (add, edit, delete) call mocked API handlers.
- Empty states display correctly.
- Loading states display correctly.
- Error states display correctly.

#### 2.2 MSW (Mock Service Worker) for API mocking
Add `msw` to devDependencies:
```bash
npm install --save-dev msw
```
Create `frontend/src/mocks/handlers.ts` with handlers for all v3.11 endpoints:
- `/api/coa/*`
- `/api/transactions/*`
- `/api/recurring/*`
- `/api/checks/*`
- `/api/inventory/*`
- `/api/fx/*`
- `/api/reconciliation/*`
- `/api/reports/*`
- `/api/budget/*`
- `/api/invoices/*`
- `/api/liabilities/*`
- `/api/investments/*`

#### 2.3 Frontend build gate
Before any B6 merge:
```bash
cd frontend
npm install
npm run build
npm run test
```
Must pass with 0 TypeScript errors and 0 test failures.

#### 2.4 Optional e2e
If approved later, add Playwright:
```bash
npm install --save-dev @playwright/test
npx playwright install
```
E2E tests cover:
- Clean install → create master password → login.
- Create a transaction in the unified register.
- Generate a P&L report.
- Export tax summary.

---

## 3. Integration / Smoke Test Harness

### Local backend smoke
```bash
python -m uvicorn backend.api:app --reload --port 8000
# or run packaged .exe
```

### Smoke checklist (per bundle)
After B1:
- `GET /api/health` returns `version: "3.11.6"`.
- `POST /api/coa/` creates an account.
- `GET /api/coa/` lists only current tenant accounts.

After B2:
- `POST /api/transactions/` creates a transaction.
- `POST /api/transactions/{id}/splits` adds splits.
- `GET /api/transactions/` supports filters/pagination.
- Recurring rule generates occurrences.
- Check register records and clears checks.

After B3:
- Inventory item receive/sell adjusts qty.
- FX rate conversion returns expected amount.
- Loan schedule generates periods.
- Investment FIFO cost basis calculates correctly.

After B4:
- OFX/CSV reconciliation import auto-matches.
- Tax export downloads signed package.
- Reports return JSON + CSV.
- Budget vs. actual report shows variance.

After B5:
- Invoice created, payment recorded, aging report accurate.
- Bill created and marked paid.

After B6:
- Browser opens to register page after login.
- Register component lists, edits, and deletes transactions.
- COA tree renders.

After B7:
- Windows `.exe` clean install smoke passes.
- Ubuntu `.deb` clean install smoke passes.
- Single-instance enforcement tested.
- macOS `.app` smoke passes if host available.

---

## 4. CI/CD Harness

### Existing state
- `.github/workflows/ci.yml` runs backend tests and packaging smoke.

### Required additions for v3.11.6
1. Frontend build + test job.
2. PostgreSQL service container for `test_rls_postgres.py`.
3. Job to build Windows installer as artifact.
4. Job to build Linux `.deb` as artifact.
5. Optional macOS build job (if runner available).

---

## 5. Infrastructure Checklist

| Resource | Status | Action |
|----------|--------|--------|
| Local SQLite tests | Ready | Use existing conftest |
| PostgreSQL test DB | Not ready | Provision Docker Postgres |
| Frontend Vitest + MSW | Partially ready | Add MSW dependency |
| Playwright e2e | Not ready | Defer until B6 beta |
| CI Windows installer artifact | Ready | Update workflow |
| CI Linux `.deb` artifact | Ready | Update workflow |
| CI macOS runner | Not ready | Defer until host available |

---

## 6. Recommended First Test Task

Before any bundle code changes, execute:
1. Add `msw` to frontend devDependencies.
2. Add `tenant` and `viewer_member` fixtures to `conftest.py`.
3. Add PostgreSQL test fixture.
4. Create `frontend/src/mocks/handlers.ts` with B1 endpoint mocks.
5. Update CI workflow to include frontend build/test job.

This gives all subsequent subagents a consistent testing substrate.
