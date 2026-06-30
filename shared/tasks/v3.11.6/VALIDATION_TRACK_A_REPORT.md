# Track A: Backend Integrity & Performance Validation Report

**Date:** 2026-06-30 01:04:58 UTC  
**Updated:** 2026-06-30 02:50 UTC  
**Branch:** `v3.11.6-dev` @ `63f628b`  
**Tester:** James Clawd

## Summary

| Section | Verdict | Details |
|---------|---------|---------|
| A.1 API Fuzz | PASS | 500 requests; 2xx=251, 4xx=249, 5xx=0 |
| A.2/A.3 Ledger Random Walk + Invariants | PASS | 250 operations; 0 invariant violations |
| A.4 Chaos/Repair | TBD | Not executed yet |
| A.5 Multi-Tenant Isolation | **PASS** | SQLite caveat documented; PostgreSQL RLS tests (6/6) pass with `taxflow_user` non-superuser |
| A.6 Bookkeeping Module Stress | TBD | Not executed yet |
| A.7 Parser Resilience Fuzz | PASS | 100 mutated files; 0 crashes |
| A.8 Concurrent Load | TBD | Not executed yet |
| A.9 Volume Soak | TBD | Not executed yet |
| A.10 Backup & Restore Integrity | INFO | `backup_restore.py` not found |
| A.11 Resource Monitoring | TBD | Not executed yet |
| A.12 Date Edge Cases | TBD | Not executed yet |
| A.99 Summary | PASS | PostgreSQL migration chain fixed; baseline subset 60/60 passed |

## Environment

- PostgreSQL 17 running on `localhost:5433`
- Database: `taxflow_test`
- User: `taxflow_user` (normal role, not superuser, to ensure RLS enforcement)
- `TEST_DATABASE_URL=postgresql://taxflow_user:taxflow_pass@localhost:5433/taxflow_test`

## A.5 Multi-Tenant Isolation — Updated Verdict

The earlier SQLite single-user "leaks" on `/api/coa/` and `/api/clients/` were expected behavior: default COA and client rows are seeded at the user level and shared across that user's clients in `TAXFLOW_SINGLE_USER=true` SQLite mode.

PostgreSQL RLS isolation is now verified independently:
- Migration chain fixed so `alembic upgrade head` completes cleanly on PostgreSQL.
- `taxflow_user` changed from `SUPERUSER` to normal role so RLS policies are enforced.
- `backend/tests/test_rls_postgres.py` updated to bind the session to a single connection, preventing GUC loss across pooled connection checkouts.
- Result: **6/6 RLS tests pass**, including tenant read isolation and cross-tenant INSERT blocking.

## Metrics

### A.1 API Fuzz
```json
{
  "2xx": 251,
  "4xx": 249,
  "5xx": 0
}
```

### A.2/A.3 Ledger Random Walk + Invariants
```json
{
  "operations": 250,
  "violations": 0,
  "violation_samples": []
}
```

### A.5 Multi-Tenant Isolation — PostgreSQL RLS
```json
{
  "checks": 6,
  "leaks": 0,
  "verdict": "PASS"
}
```

### A.7 Parser Resilience Fuzz
```json
{
  "total": 100,
  "crashes": 0
}
```

### A.99 Summary
```json
{
  "elapsed_seconds": 12.206412076950073
}
```
