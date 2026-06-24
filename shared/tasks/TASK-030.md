# TASK-030 — Asymmetric Signed Audit Entries

**Status:** COMPLETE  
**Completed:** 2026-06-21 (EDT)  
**Assignee:** Jane Clawd

## Objective
Add tamper-evident Ed25519 signatures to every audit entry so the audit chain can be independently verified by public key alone.

## Implementation

### New file: `backend/security/audit_sign.py`
- Ed25519 private key loaded from `TAXFLOW_AUDIT_PRIVATE_KEY_PATH`, or deterministic fallback from the local secret for dev/test.
- `public_key_pem()` exposes the public key for offline verification.
- `sign_entry()` signs a canonical JSON payload of the entry fields plus `chain_hash`.
- `verify_entry_signature()` verifies with the cached or supplied public key.

### Updated: `backend/audit/audit_trail.py`
- Every `record()` call now computes `chain_hash` and then signs the entry, storing the base64 signature.
- `verify_chain()` walks the table in `id` order and validates both chain hashes and Ed25519 signatures.
- Returns `(valid: bool, first_bad_id: str|None)`; first bad ID reported for both chain and signature failures.

### Updated: `backend/models.py`
- Added `signature = Column(String, nullable=True)` to `AuditEntry`.

### New Alembic migration: `alembic/versions/4f0bb0ee4bff_add_audit_entry_ed25519_signature_column.py`
- Adds the `signature` column to `audit_entries`.
- New head: `4f0bb0ee4bff`.

### Updated: `backend/schemas.py`
- `AuditEntryOut` exposes the new `signature` field.

### Updated: `backend/tests/test_migration_health.py`
- Updated expected head from `842bfa1713f4` to `4f0bb0ee4bff`.

### Updated: `.env.example`
- Added `TAXFLOW_AUDIT_PRIVATE_KEY_PATH`.

### Updated: `README.md`
- Added env var to configuration table.
- Added "Audit integrity" section documenting hash chain + Ed25519 signatures and the `/api/audit/verify` endpoint.

### New test file: `backend/tests/test_audit_sign.py`
- 7 tests:
  - public key is valid PEM
  - sign and verify a canonical entry
  - signature fails when payload is tampered
  - verification succeeds using only the public key
  - `record()` writes a valid signature
  - `verify_chain()` detects a removed signature
  - `/api/audit/verify` endpoint reports valid status

## Test Results
- `pytest backend/tests/test_audit_sign.py -v` → **7 passed, 0 failed**
- Targeted regression (audit sign + audit trail + append-only + refresh tokens + hybrid auth + API) → **62 passed, 0 failed**
- Full backend suite `pytest backend/tests -q` → **261 passed, 0 failed**

## Files Changed
- `backend/security/audit_sign.py` (new)
- `backend/audit/audit_trail.py`
- `backend/models.py`
- `alembic/versions/4f0bb0ee4bff_add_audit_entry_ed25519_signature_column.py` (new)
- `backend/schemas.py`
- `backend/tests/test_migration_health.py`
- `.env.example`
- `README.md`
- `backend/tests/test_audit_sign.py` (new)

## Notes
- No new runtime dependency beyond existing `cryptography`.
- Production should generate and protect a dedicated Ed25519 private key and use only the public key for verification.
- No commit per instruction; v3.9.2 batched commit pending.
