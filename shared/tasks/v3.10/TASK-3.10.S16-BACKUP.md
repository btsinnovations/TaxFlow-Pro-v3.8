# TASK-3.10.S16 — Backup + Disaster Recovery

**Owner:** TBD  
**Goal:** Add encrypted, integrity-verified automatic backups.

## Files

- `backend/local/backup.py`
- `scripts/backup.py`
- `scripts/restore.py`
- `backend/tests/test_backup_integrity.py`

## Requirements

1. Encrypt backup with user-derived key.
2. Add tamper-evident manifest (hash + signature).
3. Restore verifies integrity before import.
4. CLI scripts already exist; wire to backend and UI.

## Tests

- Backup creates encrypted file.
- Tampered backup rejected on restore.
- Valid backup restores correctly.

## Report

Files changed, encryption/integrity approach, test results.
