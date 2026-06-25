# Bundle 4: Global Wrap-Up — Directive for Jane

**Prerequisite:** Bundle 3 committed and full test suite green.

**Goal:** Close v3.11-dev. Finalize migration health, backup import, release notes, and version bump.

---

## 1. Alembic migration baseline (3.11.G01)

### Current state
- `alembic/versions/330eb386b9c2_add_fitid_to_transactions_for_ofx_.py` already adds `fitid` + index and `is_active` to `gl_accounts`.
- The app currently relies on `Base.metadata.create_all()` for table creation.
- **Gap:** there is no baseline migration that represents the v3.11 schema. For clean Alembic deployments we need a single baseline revision that the existing migration can depend on.

### Tasks
1. Inspect `backend/models.py` and confirm all v3.11 tables are defined (`gl_accounts`, `transactions`, `statements`, `accounts`, `categorization_rules`, `recurring_rules`, `invoices`, `bills`, `inventory_items`, `inventory_projects`, `investment_lots`, `liabilities`, `fx_rates`, `reconciliations`, `budgets`, `budget_entries`, `tax_exports`, etc.).
2. Generate a baseline migration:
   ```bash
   alembic revision --autogenerate -m "v3.11 baseline"
   ```
   (If autogenerate tries to recreate everything, switch to manual baseline: `alembic revision -m "v3.11 baseline"` and populate `upgrade()` with `op.create_table` statements only for tables that do not yet exist in a fresh v3.10 DB.)
3. Ensure `330eb386b9c2_add_fitid_to_transactions_for_ofx_.py` has `down_revision` pointing to the new baseline.
4. Test upgrade/downgrade against:
   - A fresh SQLite DB.
   - An existing v3.10-style SQLite DB (manually create one with just `gl_accounts` + `transactions` + `users`, then run upgrade).
5. Add `backend/tests/test_alembic_migrations.py`:
   - `test_upgrade_from_v3_10_db`
   - `test_upgrade_downgrade_roundtrip`
6. Expected result: both tests pass.

---

## 2. v3.10 → v3.11 backup import wizard (3.11.G02)

### Tasks
1. Create `backend/backup_import.py`.
2. Implement `import_v3_10_backup(backup_json_path, db_session, user_id)`:
   - Read the v3.10 backup JSON.
   - Map legacy `gl_accounts` → `coa_accounts` / `gl_accounts` with `type`, `number`, `name`, `description`, `is_active`.
   - Import `transactions` with FITID deduplication.
   - Import `statements`, `categorization_rules`, `recurring_rules`, `invoices`, `bills`, `inventory_items`, `liabilities`, `investment_lots`, `fx_rates` if present.
   - Idempotency: skip duplicates by FITID for transactions, by `name + number` for accounts, by rule pattern for rules.
3. Add `POST /api/backup/import` to `backend/routers/backup.py` (create router if missing).
   - Accept multipart file upload of v3.10 backup JSON.
   - Return summary: `{ imported_accounts, imported_transactions, skipped_duplicates, imported_rules, errors }`.
4. Add `backend/tests/test_backup_import.py`.
   - `test_import_v3_10_backup`
   - `test_import_is_idempotent`
5. Expected result: tests pass.

---

## 3. CHANGES.md Section 57+ (3.11.G03)

### Tasks
1. Read `CHANGES.md` from top. Confirm the last completed section is Section 56 (COA scaffold).
2. Add the following new sections:
   - **Section 57 — v3.11 Module Implementations (3.11.02–3.11.13)** — summarize roles/register/recurring + all 9 Jane modules.
   - **Section 58 — Parser Expansion & Auto-Detection (3.11.PARSER)** — 18 institutions, detect endpoint, fixtures, interface contract.
   - **Section 59 — Tax Rules Engine Search/Filter (3.11.TAXRULES)** — backend search API, frontend UI.
   - **Section 60 — OFX/QFX Import (3.11.OFX)** — dependency-free parser, FITID dedup, account mapping.
   - **Section 61 — Export UI Polish (3.11.EXPORTUI)** — remove stale labels, conditional enablement, progress indicator.
   - **Section 62 — Alembic Baseline + Backup Import (3.11.G01–G02)** — migration and backup wizard.
   - **Section 63 — v3.11.0 Version Bump (3.11.G04)**.
3. Follow the existing CHANGES.md format (files changed, files added, changes, verification command, expected result).

---

## 4. Version bump (3.11.G04)

### Tasks
1. Update `backend/version.py`: `version = "3.11.0"`.
2. Update `frontend/package.json` version to `3.11.0`.
3. Add `test_version_constant` to `backend/tests/test_version.py` (create file if missing):
   ```python
   from backend.version import version

   def test_version_is_3_11_0():
       assert version == "3.11.0"
   ```
4. Expected result: test passes.

---

## 5. Supported institutions documentation (3.11.G06)

### Tasks
1. Create or update `docs/SUPPORTED_INSTITUTIONS.md`.
2. List all 18 institutions from `backend/parsers/institution.py`.
3. Mark which have specific parsers vs. generic fallback.
4. Note input formats: PDF, CSV, OFX/QFX.
5. Include a quick-start sample for `POST /api/imports/detect`.

---

## 6. Final full-suite verification

### Tasks
1. Run backend full suite:
   ```bash
   python -m pytest backend/tests/ tests/
   ```
2. Run frontend build + tests:
   ```bash
   cd frontend
   npm run build
   npm test
   ```
3. Confirm both green before any merge.

---

## Report format
- Files changed
- Test commands + results
- Any blockers

## Constraints
- No destructive changes to existing v3.9 data paths.
- Backup import must be reversible/safe.
- Do not merge to `main` or tag `v3.11.0` without explicit approval from James / Josh.
