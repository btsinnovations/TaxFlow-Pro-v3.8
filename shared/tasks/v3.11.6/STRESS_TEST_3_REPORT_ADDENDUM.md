# Stress Test 3 — Addendum: PostgreSQL RLS Re-verification

**Date:** 2026-07-01 (UTC) / 2026-06-30 EDT  
**Investigator:** James Clawd  
**Status:** Root cause identified; not a production code bug.

---

## Corrected Diagnosis

Jane’s Stress Test 3 report flagged 3/6 PostgreSQL RLS tests as FAILED with cross-tenant access. After independent reproduction, the failures were traced to the **test role**, not to `backend/rls.py` or the RLS migration.

### Original failing configuration
```
TEST_DATABASE_URL=postgresql+psycopg2://postgres@localhost:5433/taxflow_stress_test
```
The role `postgres` is a **superuser**. PostgreSQL superusers bypass Row-Level Security **even when `FORCE ROW LEVEL SECURITY` is enabled**. Therefore the RLS policies were present and correct, but the connecting role ignored them.

### Verified passing configuration
```
TEST_DATABASE_URL=postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_test
```
The role `taxflow_test` is **not a superuser**. With this role the RLS tests pass cleanly:

```text
6 passed, 29 warnings in 3.30s
```

### Minimal confirmation
A standalone SQL reproduction using a superuser role with a forced-RLS table and an explicit `taxflow.tenant_id` GUC returned both tenant rows, proving the role bypass:

```text
With tenant_id=1: [(1, 1, 't1'), (2, 2, 't2')]
Without tenant_id: [(1, 1, 't1'), (2, 2, 't2')]
```

---

## Revised Verdict

**PostgreSQL RLS enforcement is functional.** The earlier failure was an artifact of testing with a superuser role.

- SQLite deployments: **GO**
- PostgreSQL multi-tenant deployments: **GO** — provided the application DB role is not `SUPERUSER` and does not have `BYPASSRLS`.

## Recommended Action

A single safe production hardening is recommended (requires Josh approval before implementation):

- Add a startup check in `backend/database.py` (or `backend/rls.py`) that refuses to initialize multi-tenant PostgreSQL mode if the connected role has `rolsuper=true` or `rolbypassrls=true`. Log a clear, fatal error: `TaxFlow multi-tenant mode cannot run with a PostgreSQL superuser or BYPASSRLS role.`

No changes to RLS policies, session lifecycle, or `backend/rls.py` are required.

---

## Files Not Modified

- `backend/rls.py` — not modified
- `backend/database.py` — not modified
- `alembic/versions/*.py` — not modified
- `backend/tests/test_rls_postgres.py` — not modified

*Addendum compiled by James Clawd after independent reproduction.*
