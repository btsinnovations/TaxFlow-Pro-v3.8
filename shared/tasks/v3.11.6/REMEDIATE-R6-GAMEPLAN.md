# R6 — Cleanup, Quality, and Trust-Signal Fixes Gameplan

**Branch:** `v3.11.6-dev-REMEDIATE-R6-cleanup`
**Base branch:** `v3.11.6-dev` (already contains merged R1–R5)
**Goal:** Fix the two critical blockers from the R6 validation report and complete all cleanup tasks so `v3.11.6-dev` is deployable.

---

## Critical Blockers (must fix first)

### CB1. Alembic `downgrade base` fails on SQLite + PostgreSQL
**Evidence:** `alembic downgrade base` fails with `no such index: ix_trained_models_user_id` because migration `f1a2b3c4d5e6` drops the `trained_models` table before migration `d9cf7c4a8fdf` tries to drop its indexes.

**Fix file:** `alembic/versions/d9cf7c4a8fdf_add_trained_models_table.py`
- Make `downgrade()` idempotent by using `DROP INDEX IF EXISTS` via raw SQL or inspector check.

**Verify:**
```bash
alembic downgrade base
alembic upgrade head
alembic downgrade base
alembic upgrade head
```
All four commands must pass on both SQLite and PostgreSQL.

### CB2. App startup crash on existing `taxflow.db`
**Evidence:** `taxflow.db` has `alembic_version = d9cf7c4a8fdf` but no data tables. `backend/api.py:run_migrations()` calls `alembic upgrade head`, which tries `ALTER TABLE transactions ADD COLUMN ...` and fails because the table does not exist.

**Fix file:** `backend/api.py`
- Add a startup guard: if `alembic_version` table exists but no data tables exist, stamp to `base` and run `upgrade head`.
- Keep behavior unchanged for normal databases.

**Verify:**
```bash
# Simulate corrupted state
mv taxflow.db taxflow.db.bak
python -c "import sqlite3; c=sqlite3.connect('taxflow.db'); c.execute('CREATE TABLE alembic_version (version_num VARCHAR)'); c.execute('INSERT INTO alembic_version VALUES (?)', ('d9cf7c4a8fdf',)); c.commit()"
python -c "import backend.api"  # must not crash
```

---

## High-Priority Cleanup Tasks

### H1. Bump version to `3.11.6`
**Files:**
- `version.txt`
- `backend/version.py` (if exists)
- `frontend/package.json` (if version field exists)
- `CHANGES.md` Section 70+ summary

### H2. Update `docs/SUPPORTED_INSTITUTIONS.md`
**Draft:** `shared/tasks/v3.11.6/SUPPORTED_INSTITUTIONS_UPDATE.md`
**Requirement:** List all 27 specific parsers in `backend/parsers/*.py`.

### H3. Delete orphaned patch/debug files
**Files to delete from project root:**
- `patch2.py`, `patch3.py`, `patch4.py`, `patch5.py`
- `patch_brute_all.py`
- `patch_helper.py`
- `patch_subtasks.py`
- `patch_success_reset.py`, `patch_success_reset2.py`
- `test_pg_conn.py`
- `conftest_debug_out.txt`
- `pytest_out.txt`, `pytest_pipeline_results.txt`, `pytest_sqlite_results.txt`
- `setup_first_run.py` (verify not imported anywhere first)
- `backend/tests/conftest_debug.py` through `conftest_debug6.py`

### H4. Frontend mock data excluded from production builds
**Files:**
- `frontend/vite.config.ts`
- `frontend/src/data/mockData.ts`
- `frontend/src/mocks/*`

**Approach:** Use `import.meta.env.DEV` guards in mock consumers, or configure Vite `build.rollupOptions.external` / `define` to exclude mock modules in production.

### H5. Cash flow statement basis parameter
**Files:**
- `backend/routers/reports.py`
- `backend/accounting/reports.py`
- Add tests in `backend/tests/test_reports.py`

**Requirement:** `GET /api/reports/cash-flow?basis=cash|accrual` (default `accrual` for backward compatibility). True cash basis computes operating cash from actual cash-account GL entries.

### H6. Clean code-smell comments
**Files:**
- `backend/accounting/budget.py:87` — replace "Stub" comment
- `backend/accounting/coa.py:112` — replace "placeholder" comment
- `backend/accounting/reports.py` — clarify accrual-proxy cash flow comment

### H7. Update docs
**Files:**
- `CHANGES.md` — Section 70+ documenting R1–R6 remediation
- `docs/KNOWN_ISSUES.md` — remove fixed items
- `docs/TODO_FIRST.md` — update or delete if stale

---

## Validation Plan

After all changes:
1. `alembic upgrade head` on fresh SQLite
2. `alembic downgrade base` on SQLite
3. `alembic upgrade head` on SQLite
4. Repeat 1–3 on PostgreSQL
5. Simulate corrupted `taxflow.db` startup
6. Run focused regression batches covering R1–R5 (target 110+ tests)
7. Run orphaned-file search and confirm clean
8. Confirm `version.txt` reads `3.11.6`
9. Confirm `SUPPORTED_INSTITUTIONS.md` lists 27 parsers
10. Confirm frontend production build excludes mocks

---

## Deliverables

- All commits on `v3.11.6-dev-REMEDIATE-R6-cleanup`
- Push branch to origin
- Do NOT merge to `v3.11.6-dev` without James/Josh approval
- Report results to this session with branch HEAD SHA and test counts
