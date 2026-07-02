# ST4 Phases 4.3, 6, & 7 — Test Playbook

**Branch:** `v3.11.6-dev`  
**Date:** 2026-07-01  
**Owner:** Jane Clawd (execution) / James Clawd (planning)

---

## Phase 4.3 — Heavy Compute & Report Generation Queueing

### Scripts
- `st4_p4_3_seed.py` — seeds fresh DB `st4_p43` with 5 users, 5 tenants, 2 statements each, ~200 txns each.
- `st4_p4_3_report_queue.py` — fires 20 concurrent report requests across 5 users.

### Run
```powershell
cd "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9"
$env:PYTHONPATH = "."
$env:DATABASE_URL = "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_stress_4_p43"
python st4_p4_3_seed.py
python -m backend.api
# new terminal:
$env:PYTHONPATH = "."
$env:ST4_TEST_DB = "taxflow_stress_4_p43"
python st4_p4_3_report_queue.py
```

### Expected Findings
- No queue / thread pool / background task system for reports.
- DB pool max 15; 20 concurrent requests may cause connection timeouts.
- Year-end-package (zip of 13 files) is the heaviest load.

### Success Criteria
- All 20 requests complete or fail gracefully (no 500).
- No OOM / pool exhaustion crashes.
- No orphaned temp files.

---

## Phase 6.1 — Pagination & Cursor Exhaustion

### Scripts
- `st4_p6_seed.py` — seeds DB `st4_p61` with 500K transactions for one tenant.
- `st4_p6_1_pagination.py` — requests deep pages (1, 100, 1k, 10k, past-end).

### Run
```powershell
$env:PYTHONPATH = "."
$env:DATABASE_URL = "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_stress_4_p61"
python st4_p6_seed.py
python -m backend.api
# new terminal:
$env:PYTHONPATH = "."
$env:ST4_TEST_DB = "taxflow_stress_4_p61"
python st4_p6_1_pagination.py
```

### Success Criteria
- Deep pages return in <50 ms each.
- Past-end page returns empty gracefully (not 500).

---

## Phase 6.2 — Schema Migration Under Load

### Script
- `st4_p6_2_migration.py` — runs `alembic upgrade head` while API reads/writes run concurrently.

### Setup
- Use DB stamped to pre-v3.11.6 migration revision.
- Seed with 100K transactions first (reuse `st4_p6_seed.py` with DB `st4_p62`).

### Run
```powershell
$env:DATABASE_URL = "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_stress_4_p62"
alembic downgrade f98993328938  # pre-column-type migration
python st4_p6_seed.py  # seed 100K
python -m backend.api
# new terminal:
$env:PYTHONPATH = "."
$env:ST4_TEST_DB = "taxflow_stress_4_p62"
python st4_p6_2_migration.py
```

### Expected Finding
- `f98993328938` migration rewrites `periods.start_date/end_date` with `ACCESS EXCLUSIVE` lock.
- Background reads may block; verify no deadlocks or 500s.

---

## Phase 7.x — Document Ingestion Edge Cases

### Scripts
- `st4_p7_seed.py` — fresh DB `st4_p7` with one user.
- `st4_p7_1_layout_drift.py` — 6 PDF mutations.
- `st4_p7_2_ocr.py` — degraded/scanned PDF with noise + blur.
- `st4_p7_3_frankenstein.py` — 12-page mixed marketing + checking + T&C + savings PDF.
- `st4_p7_4_neobank.py` — unknown institution fallback.

### Run
```powershell
$env:PYTHONPATH = "."
$env:DATABASE_URL = "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_stress_4_p7"
python st4_p7_seed.py
python -m backend.api
# new terminal:
$env:PYTHONPATH = "."
$env:ST4_BASE_URL = "http://localhost:8000"
python st4_p7_1_layout_drift.py
python st4_p7_2_ocr.py
python st4_p7_3_frankenstein.py
python st4_p7_4_neobank.py
```

### Success Criteria
- No 500s from any mutated PDF.
- OCR-degraded PDF sets `needs_review=True` or returns gracefully.
- Frankenstein PDF does not leak transactions between accounts.
- Unknown neobank returns `needs_review=True` with no crash.

---

## Governance
- Log all failures; do not patch production code mid-test.
- Report architectural gaps for review.
- No commits/pushes for ST4 scripts.
