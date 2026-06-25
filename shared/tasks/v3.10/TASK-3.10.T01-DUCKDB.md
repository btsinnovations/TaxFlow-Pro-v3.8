# TASK-3.10.T01 — DuckDB Export Engine

**Owner:** TBD  
**Goal:** Replace hand-built export generation in `backend/routers/export.py` with DuckDB SQL-driven exports.

## Files

- `backend/services/duckdb_export.py` — new DuckDB export engine
- `backend/routers/export.py` — refactor to delegate to DuckDB engine
- `backend/tests/test_duckdb_export.py`

## Requirements

1. DuckDB reads from the existing SQLite database via SQLAlchemy or direct attach.
2. Support CSV, JSON, Parquet, Excel, and PDF summary generation via DuckDB queries.
3. Preserve exact output schemas currently expected by frontend/tests.
4. No telemetry or network calls.

## Tests

- Export CSV matches current output.
- Export Excel opens and contains expected sheets.
- Export Parquet round-trips.
- Export JSON matches current schema.
- PDF summary still generates (may keep current generator or replace with query + template).

## Report

When complete: files changed, test command + result, performance comparison if measured.
