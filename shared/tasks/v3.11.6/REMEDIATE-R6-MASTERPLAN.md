# R6 — Cleanup, Quality, and Trust-Signal Fixes Masterplan

## Objective
Fix Alembic downgrade bug, version mismatch, outdated docs, delete orphaned files, and harden frontend production build.

## Branch
`v3.11.6-dev-REMEDIATE-R6-cleanup` (already pushed to origin)

## Background from Code Research
- `version.txt` currently says `3.11.5`.
- `docs/SUPPORTED_INSTITUTIONS.md` lists 18 institutions; 27 parsers exist.
- Orphaned patch/debug files in project root.
- Alembic migration `d9cf7c4a8fdf` downgrade fails trying to drop non-existent index `ix_trained_models_user_id`.

## Tasks

### 1. Fix Alembic Downgrade
- Inspect migration `d9cf7c4a8fdf` and adjacent migrations.
- Make `op.drop_index()` idempotent:
  - Option A: use raw `DROP INDEX IF EXISTS` for PostgreSQL; for SQLite, use `IF EXISTS` or try/except block.
  - Option B: verify index exists via inspector before dropping.
- Test on fresh SQLite and PG:
  - `alembic upgrade head`
  - `alembic downgrade base`
  - `alembic upgrade head`
- Add migration-health test for downgrade base.

### 2. Fix `test_api_balance_sheet` Token Expiry
- Locate test in `backend/tests/test_api.py` or similar.
- Use a longer-lived test token, refresh token mid-test, or split into smaller fast tests.
- Verify full suite passes reliably.

### 3. Update `version.txt`
- Change `3.11.5` → `3.11.6`.

### 4. Update `docs/SUPPORTED_INSTITUTIONS.md`
- List all 27 specific parsers.
- Include layout family note for the 103-institution registry.
- Clean up the garbled characters in the current table.

### 5. Delete Orphaned Files
Delete from project root:
- `patch2.py`, `patch3.py`, `patch4.py`, `patch5.py`
- `patch_brute_all.py`
- `patch_helper.py`
- `patch_subtasks.py`
- `patch_success_reset.py`, `patch_success_reset2.py`
- `test_pg_conn.py`
- `conftest_debug_out.txt`
- `pytest_out.txt`, `pytest_pipeline_results.txt`, `pytest_sqlite_results.txt`
Move or delete `setup_first_run.py`.

### 6. Frontend Mock Cleanup
- Ensure `frontend/src/data/mockData.ts` and `frontend/src/mocks/` are excluded from production builds.
- Use `import.meta.env.DEV` guards or Vite `define` to strip.
- Add build validation step.

### 7. Improve Cash Flow Statement
- Add `basis=cash|accrual` query parameter to `/api/reports/cash-flow`.
- True cash basis: compute operating cash from actual cash-account GL entries.
- Keep simplified accrual proxy as default for backward compatibility.

### 8. Clean Up Code Smell Comments
- Replace "Stub" / "placeholder" comments in `budget.py`, `coa.py`, `reports.py` with accurate descriptions.

### 9. Docs Refresh
- Update `CHANGES.md` Section 70+ to list remediation work.
- Update `docs/KNOWN_ISSUES.md` to remove fixed items.
- Update `docs/TODO_FIRST.md` if still referenced.

## Acceptance Criteria
- [ ] `alembic downgrade base` passes on fresh SQLite and PostgreSQL.
- [ ] `pytest backend/tests` passes on both backends with 0 failures.
- [ ] Orphaned files deleted; `git status` clean.
- [ ] `version.txt` reads `3.11.6`.
- [ ] `SUPPORTED_INSTITUTIONS.md` lists all 27 parsers cleanly.
- [ ] Frontend production build excludes mock data.
- [ ] Cash flow endpoint supports `basis=cash`.

## Files Likely to Change
- `alembic/versions/d9cf7c4a8fdf*.py` or new fixup migration
- `version.txt`
- `docs/SUPPORTED_INSTITUTIONS.md`
- `docs/KNOWN_ISSUES.md`
- `docs/TODO_FIRST.md`
- `CHANGES.md`
- `backend/accounting/budget.py`
- `backend/accounting/coa.py`
- `backend/accounting/reports.py`
- `frontend/vite.config.ts` or build script
- `frontend/src/data/mockData.ts`
- `frontend/src/mocks/*`

## Dependencies
- Must run after R1-R5 merge to capture all schema/model changes in docs and version.
