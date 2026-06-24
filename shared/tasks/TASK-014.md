# TASK-014 — P0.3 Tamper-Aware Audit Log Integrity Verification

## Status
**COMPLETE** — all deliverables implemented, tests passing, migration reversible.

## Files Changed
- `backend/audit/audit_trail.py` — added:
  - `chain_hash` computation (`SHA-256(previous chain_hash + canonical JSON)`)
  - `verify_chain(db) -> Tuple[bool, Optional[str]]`
  - `backfill_chain_hashes(db) -> int`
  - kept legacy `entry_hash` unchanged
- `backend/models.py` — added nullable `chain_hash` column to `AuditEntry`.
- `backend/routers/audit.py` — updated `GET /api/audit/verify` to return `{valid, first_bad_id, count}` for authenticated users.
- `backend/schemas.py` — added `chain_hash` to `AuditEntryOut`.
- `backend/tests/test_audit_trail.py` — updated for new `verify_chain` signature and added tests for clean chain, tamper detection, NULL backfill, and the verify endpoint.
- `alembic/versions/c4062c0c95ff_add_audit_chain_hash.py` *(new)* — adds `chain_hash` column and deterministically backfills existing rows; downgrade drops the column.
- `README.md` — updated Audit Trail bullet and Stage 2 section to mention `GET /api/audit/verify` tamper-detection.

## Test Results
```
pytest backend/tests/test_audit_trail.py -v
6 passed, 0 failed
```

```
pytest backend/tests/test_audit_trail.py backend/tests/test_keyring_secret.py backend/tests/test_hybrid_auth.py -v
39 passed, 0 failed
```

```
pytest backend/tests/test_api.py -v
13 passed, 0 failed
```

Migration upgrade and downgrade verified on a temporary SQLite database.

## Blockers
None.

## Notes
- Canonical JSON uses sorted keys, compact separators (`(',',':')`), UTC ISO timestamps, and SHA-256.
- `tenant_id` is encoded as `None` in the canonical JSON because `AuditEntry` does not currently have a `tenant_id` column; `user_id` maps to `actor_id`.
- No existing audit record semantics changed; only `chain_hash` and verification helpers were added.
- No commit made per instruction; awaiting v3.9.2 batch commit.
