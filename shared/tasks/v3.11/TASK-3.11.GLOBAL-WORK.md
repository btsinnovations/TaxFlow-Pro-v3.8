# TASK-3.11.G — Global Tasks

**Owner:** Jane  
**Goal:** Complete Alembic migration, backup import wizard, CHANGES.md, version bump, parser normalization, and docs.

## Files

- `alembic/versions/` — add migration.
- `backend/backup_import.py` or similar — create v3.10→v3.11 backup import wizard.
- `CHANGES.md` — add Section 50+ for v3.11.
- `backend/version.py` or `package.json` + `pyproject.toml` — bump to `3.11.0`.

## Tasks

1. **Alembic migration (3.11.G01)**
   - Create new `coa_accounts` table.
   - Add `fitid` column to `transactions`.
   - Add new v3.11 tables if not already present via model sync.
   - Provide upgrade/downgrade paths.
   - Test migration against fresh and existing SQLite DBs.

2. **Backup import wizard (3.11.G02)**
   - Read v3.10 backup JSON.
   - Map legacy `gl_accounts` → `coa_accounts`.
   - Import transactions, statements, rules, invoices, etc.
   - Idempotent: skip duplicates by FITID/rule signature.

3. **CHANGES.md (3.11.G03)**
   - Section 50+ summarizing all v3.11 features.

4. **Version bump (3.11.G04)**
   - Update backend version constant and frontend `package.json`.

5. **Parser normalization (3.11.G05)**
   - Ensure all parsers implement the common interface used by auto-detection.

6. **Supported institutions docs (3.11.G06)**
   - Update `docs/SUPPORTED_INSTITUTIONS.md`.

7. **Hero/branding count (3.11.G07)**
   - Update institution count in landing page.

## Tests

- `test_alembic_migrations_up_down`
- `test_backup_import_v3_10_to_v3_11`
- `test_version_constant`

## Constraints

- No destructive changes to existing v3.9 data paths.
- Backup import must be reversible/safe.

## Report

Files changed, test command + result, blockers.
