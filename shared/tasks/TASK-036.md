# TASK-036 — Close Phase 1/2 Gaps + Release Readiness

**Status:** ✅ Complete  
**Owner:** Jane  
**Date:** 2026-06-22  
**Scope:** Approved Option 1 — v3.9.1 tree is authoritative. Close remaining Phase 1/2 cleanup gaps and verify release readiness.

---

## Phase 1/2 Gap Checklist

| # | Task | Target | Status | Notes |
|---|------|--------|--------|-------|
| 1.1 | Add `.env.example` | Root `.env.example` | ✅ Done | Already present and updated in v3.9.1 |
| 1.2 | Validate baseline migration against live PostgreSQL | `alembic/versions/d75a7eba9fd0_baseline_schema.py` | ✅ Done | Temporary PostgreSQL 16 in WSL Ubuntu; `alembic upgrade head` passes. Root-cause bug fixed in `backend/audit/append_only.py` (SQLite listener on Postgres). |
| 1.3 | Make merchant alias matching configurable | `phase3_pipeline/categorizer.py`, `categories.yaml` | ✅ Done | Added `alias_matching` config block with `default_mode` and per-merchant `overrides` |
| 2.1 | Validate PostgreSQL RLS policies end-to-end | `backend/rls.py`, RLS migration | ✅ Done | `smoke_postgres.py` SQL-level isolation test passes; cross-tenant access blocked by `tenant_id_matches` policy |
| 2.2 | Complete parser unification | `backend/parsers/`, `phase3_pipeline/pdf_parser.py` | ✅ Done | Canonical backend API + phase3 wrapper |
| 2.3 | Exercise `/api` + `X-Tenant-ID` under real Postgres | Full upload/export flow | ✅ Done | `smoke_postgres.py` API-level smoke test passes against Postgres via FastAPI `TestClient` |

---

## Completed Work

### 1.3 — Merchant Alias Matching Configuration

**Files changed:**
- `phase3_pipeline/categorizer.py`
- `categories.yaml`
- `tests/test_parsers.py`
- `tests/test_aliases.yaml`

**What was done:**
- Added top-level `alias_matching` block to `categories.yaml`:
  - `default_mode: strict`
  - `overrides` for `PAYPAL`, `SQUARE`, `GOOGLE` → `substring`
- `categorizer.py` now reads the mode, compiles aliases as start-anchored (`strict`) or substring (`substring`), and only applies substring aliases in the fallback pass.
- Updated test fixture and `test_alias_normalization_with_fixture` to assert both modes.

**Verification:**
```bash
python -m pytest tests/test_parsers.py -v
1 passed, 0 failed
```

---

## PostgreSQL Validation Results

A temporary PostgreSQL 16 server was installed in WSL Ubuntu and configured with a non-superuser application role `taxflow_app`. The v3.9 migration chain was run from base to head (`4f0bb0ee4bff`) and an end-to-end smoke test was executed.

### Migrations

```text
alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> d75a7eba9fd0, baseline schema
INFO  [alembic.runtime.migration] Running upgrade d75a7eba9fd0 -> b9f4e2c8d310, enable postgresql row level security
INFO  [alembic.runtime.migration] Running upgrade b9f4e2c8d310 -> e8b7c1d5f3a2, Add audit entries and depreciation assets
INFO  [alembic.runtime.migration] Running upgrade b9f4e2c8d310 -> c3a1f7e9d220, add local auth columns to users
INFO  [alembic.runtime.migration] Running upgrade c3a1f7e9d220, e8b7c1d5f3a2 -> 377bb18e5f7c, merge local auth and v3.9 services heads
INFO  [alembic.runtime.migration] Running upgrade 377bb18e5f7c -> a1b2c3d4e5f6, Add Stage 3 rules, flags, GL accounts, and workpaper refs
INFO  [alembic.runtime.migration] Running upgrade a1b2c3d4e5f6 -> d2e3f4a5b6c7, Add date columns, cascade constraints, and tighten user_id
INFO  [alembic.runtime.migration] Running upgrade d2e3f4a5b6c7 -> 1116e8143fc6, add revoked_tokens table
INFO  [alembic.runtime.migration] Running upgrade 1116e8143fc6 -> 2227f9254a8b, add audit description and redaction support
INFO  [alembic.runtime.migration] Running upgrade 2227f9254a8b -> f2a9b8c1d4e5, add refresh_tokens table
INFO  [alembic.runtime.migration] Running upgrade 2227f9254a8b -> c4062c0c95ff, add audit chain_hash
INFO  [alembic.runtime.migration] Running upgrade c4062c0c95ff, f2a9b8c1d4e5 -> 842bfa1713f4, merge audit chain hash and refresh token heads
INFO  [alembic.runtime.migration] Running upgrade 842bfa1713f4 -> 4f0bb0ee4bff, add audit entry Ed25519 signature column
```

### Smoke Test (`smoke_postgres.py`)

```text
Runtime PostgreSQL: True
SQL-level RLS isolation: PASS
API-level X-Tenant-ID isolation: PASS
Migration health /api/health: PASS
PostgreSQL smoke test: ALL PASS
```

### Additional Migration Bugs Fixed for PostgreSQL

1. **`backend/audit/append_only.py`**: Global `Engine.connect` listener was running SQLite-only introspection SQL (`SELECT 1 FROM sqlite_master WHERE type='table' AND name=?`) on every connection, including psycopg2. Added `_is_postgres()` helper and guarded the listener, `_has_table()`, and `install_append_only_triggers()` so Postgres connections are not touched by SQLite logic.
2. **`alembic/versions/b9f4e2c8d310_enable_postgresql_row_level_security.py`**: Moved `CREATE SCHEMA IF NOT EXISTS taxflow` to the top so the `taxflow.tenant_id_matches(integer)` function can be created without `UndefinedObject` errors.
3. **`alembic/versions/a1b2c3d4e5f6_add_stage3_rules_flags_gl_workpaper.py`**: Replaced boolean `server_default=sa.text('1')` / `sa.text('0')` with cross-dialect `server_default=sa.true()` / `sa.false()`.
4. **`alembic/versions/d2e3f4a5b6c7_add_date_columns_and_cascade_constraints.py`**: Added `postgresql_using=f"{col}::date"` for `batch_op.alter_column(..., type_=sa.Date())` conversions, and rewrote `_cascade_fk()` to drop/recreate named constraints on PostgreSQL while remaining idempotent on SQLite.

### Schema Note

All user tables are created in the default `public` schema by the migration scripts. The `taxflow` schema is reserved for RLS helper objects (e.g., `tenant_id_matches`). During validation, the application role `taxflow_app` required `search_path = public, taxflow` because some migration-generated helper logic references `taxflow.tenant_id_matches`. This is a runtime role setting, not a code change, and does not affect the canonical schema placement of tables.

## Current Test Results

### SQLite Regression Suite

```bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
python -m pytest backend/tests tests -q
346 passed, 97 warnings in 194.89s (0:03:14)
```

### PostgreSQL Smoke Test

```bash
.\run_smoke_pg.bat
PostgreSQL smoke test: ALL PASS
```

### Alembic Head

```text
4f0bb0ee4bff -> add audit entry Ed25519 signature column (head)
```

## Recommendations

1. ✅ All Phase 1/2 release-readiness items are now closed.
2. v3.9.1 can be tagged and released.
3. Phase 3 work remains gated pending Josh approval.

## Files Changed in This Task

- `phase3_pipeline/categorizer.py`
- `categories.yaml`
- `tests/test_parsers.py`
- `tests/test_aliases.yaml`
- `backend/audit/append_only.py`
- `alembic/versions/b9f4e2c8d310_enable_postgresql_row_level_security.py`
- `alembic/versions/a1b2c3d4e5f6_add_stage3_rules_flags_gl_workpaper.py`
- `alembic/versions/d2e3f4a5b6c7_add_date_columns_and_cascade_constraints.py`
- `backend/api.py`
- `smoke_postgres.py`
- `run_smoke_pg.bat`
- `CHANGES.md`
- `shared/tasks/TASK-036.md` (this file)

## Temporary PostgreSQL Environment Cleanup

The temporary PostgreSQL service in WSL Ubuntu was torn down after validation:

- Dropped database `taxflow`
- Dropped role `taxflow_app`
- Dropped role `taxflow`
- Stopped `postgresql.service`

Package removal was intentionally deferred (optional) to avoid changing installed system packages.

**Status:** ✅ Complete

## Next Step

Phase 3 work remains gated pending Josh approval. No further action unless directed.
