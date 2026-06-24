# TASK-025: TaxFlow Pro v3.9.2 — Append-only Audit + DB Triggers

## Status
**Completed** 2026-06-21

## Goal
Make `audit_entries` append-only at the database level and add DB triggers that prevent UPDATE/DELETE on the audit log while still allowing inserts and the single legitimate chain_hash self-update during record creation.

## Files Changed
- `backend/audit/append_only.py` (new) — SQLAlchemy engine-level guards, SQLite auto-trigger installation on connect, PostgreSQL trigger SQL, and a management-only `_set_audit_entries_mutable()` context manager.
- `backend/audit/audit_trail.py` — wraps the `record()` commit in `_set_audit_entries_mutable()` so the chain_hash self-update is permitted.
- `backend/audit/__init__.py` — exports `install_append_only_triggers` and `_set_audit_entries_mutable`.
- `backend/database.py` — installs append-only triggers on engine creation.
- `backend/tests/test_append_only.py` (new) — verifies INSERTs still work, UPDATEs are blocked, DELETEs are blocked.
- `backend/tests/test_audit_trail.py` — adjusted tampering test to assert the append-only guard blocks mutation rather than silently allowing it.

## Test Results
- `pytest backend/tests/test_append_only.py backend/tests/test_audit_trail.py -v` → **9 passed, 0 failed**
- Combined targeted regression run (audit + append-only + secret scan + vuln scan + upload + parser sandbox + backup + keyring + hybrid auth) → **81 passed, 0 failed**

## Notes
- SQLite uses `executescript()` on every connection to create AFTER UPDATE/DELETE triggers if `audit_entries` exists.
- PostgreSQL requires `install_append_only_triggers(engine)` to be called from an Alembic migration (supplied function returns raw PostgreSQL trigger/function DDL).
- The `before_cursor_execute` listener is intentionally narrow and exempts INSERT, SELECT, PRAGMA, CREATE, DROP, and chain_hash self-UPDATEs.
- No commit yet per orchestrator instruction; all v3.9.2 changes remain batched.
