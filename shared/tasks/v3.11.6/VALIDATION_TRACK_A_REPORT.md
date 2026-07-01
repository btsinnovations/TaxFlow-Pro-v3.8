# Track A: Backend Integrity & Performance Validation Report

**Date:** 2026-06-30 01:04:58 UTC  
**Updated:** 2026-06-30 15:08 UTC  
**Branch:** `v3.11.6-dev` @ `ab65774`  
**Tester:** James Clawd (subagent)

## Summary

| Section | Verdict | Details |
|---------|---------|---------|
| A.1 API Fuzz | PASS | 500 requests; 2xx=251, 4xx=249, 5xx=0 |
| A.2/A.3 Ledger Random Walk + Invariants | PASS | 250 operations; 0 invariant violations |
| A.4 Chaos/Repair | **PASS** | 20/20 chaos ledger writes accepted; 0 unexpected errors |
| A.5 Multi-Tenant Isolation | **PASS** | SQLite caveat documented; PostgreSQL RLS tests (6/6) pass with `taxflow_user` non-superuser |
| A.6 Bookkeeping Module Stress | **PASS** | 50/50 bulk adjusting entries created successfully |
| A.7 Parser Resilience Fuzz | PASS | 100 mutated files; 0 crashes |
| A.8 Concurrent Load | **PASS** | 100 concurrent requests; p95 latency 207 ms |
| A.9 Volume Soak | **PASS** | 1000 sequential requests in 8.35 s (119.8 req/s); 0 failures |
| A.10 Backup & Restore Integrity | **PASS** | Export/import round-trip succeeds; idempotent user/client mapping preserved |
| A.11 Resource Monitoring | **PASS** | `/api/health/public`, `/api/health/bootstrap`, `/health` all 200 |
| A.12 Date Edge Cases | **PASS** | 6/6 edge dates (leap day, year-end, 9999-12-31, etc.) accepted |
| A.99 Summary | **PASS** | All Track A sections executed; no failures |

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

### A.4 Chaos/Repair
```json
{
  "steps": 20,
  "ok": 20,
  "rejected": 0,
  "errors": []
}
```

### A.6 Bookkeeping Module Stress
```json
{
  "total": 50,
  "success": 50,
  "failure_statuses": []
}
```

### A.8 Concurrent Load
```json
{
  "requests": 100,
  "failed": 0,
  "latency_min_ms": 62.392,
  "latency_max_ms": 242.263,
  "latency_mean_ms": 157.446,
  "latency_p95_ms": 207.342
}
```

### A.9 Volume Soak
```json
{
  "requests": 1000,
  "elapsed_seconds": 8.35,
  "rps": 119.76,
  "failures": 0
}
```

### A.10 Backup & Restore Integrity
```json
{
  "exported_users": 1,
  "exported_clients": 1,
  "imported_users": 0,
  "imported_clients": 0,
  "id_maps_user_count": 1
}
```
Note: second import of same users/clients correctly maps to existing records (idempotent).

### A.11 Resource Monitoring
```json
{
  "/api/health/public": 200,
  "/api/health/bootstrap": 200,
  "/health": 200
}
```

### A.12 Date Edge Cases
```json
{
  "dates": 6,
  "ok": 6,
  "failures": []
}
```

### A.99 Summary
```json
{
  "elapsed_seconds": 12.206412076950073,
  "missing_sections_run_at": "2026-06-30T15:08:03.742395+00:00",
  "harness": "shared/tasks/v3.11.6/track_a_missing_sections.py",
  "harness_results_json": "shared/tasks/v3.11.6/track_a_missing_sections.json"
}
```
