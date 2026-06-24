# TASK-020 — P0.3 Encrypted Backups by Default

## Status
**COMPLETE** — default encrypted backup/restore implemented and all targeted tests passing.

## Files Changed
- `backend/crypto/backup_crypto.py` *(new)* — `encrypt_backup`, `decrypt_backup`, `derive_backup_key` helpers, plus convenience `encrypt_backup_with_secret` / `decrypt_backup_with_secret` wrappers.
- `backend/local/backup.py` — `backup_db()` now writes `.tfebackup` files encrypted with a key derived from the current local secret; `restore_db()` auto-detects encrypted vs plaintext and decrypts using the current local secret. Plaintext path kept behind `plaintext=True` with deprecation warnings.
- `scripts/backup.py` — added `--plaintext` flag; default is encrypted.
- `scripts/restore.py` — added `--plaintext` flag; auto-detects format and fails clearly on wrong local secret.
- `backend/tests/test_backup_restore.py` — updated + expanded: encrypted round-trip, secret-change failure, plaintext compatibility, tampered encrypted/plaintext failures, and crypto helper unit tests.
- `README.md` — added Backup & Restore section documenting encryption, same-machine restore, self-describing TFBU header, and deprecated plaintext fallback.

## Test Results
```
pytest backend/tests/test_backup_restore.py -v
7 passed, 0 failed
```

```
pytest backend/tests/test_backup_restore.py backend/tests/test_audit_trail.py backend/tests/test_keyring_secret.py backend/tests/test_hybrid_auth.py backend/tests/test_api.py -v
59 passed, 0 failed
```

## Blockers
None.

## Notes
- Authenticated encryption: Fernet (AES-128-CBC + HMAC) from `cryptography`.
- Key derivation: PBKDF2-HMAC-SHA256, **480,000 iterations**, 32-byte random salt, URL-safe base64-encoded 32-byte key.
- Backup file format: `TFBU` magic (4 bytes) + version (1 byte) + salt length (2 bytes) + salt + ciphertext.
- Default backups are encrypted; plaintext backups are deprecated but still work with warnings.
- Restore fails with a clear `BackupError` if the local secret has changed.
- `cryptography` was already present in `requirements.txt`; no new dependency needed.
- No commit made per instruction; awaiting v3.9.2 batch commit.
