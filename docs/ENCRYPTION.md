# TaxFlow Pro — Local Database Encryption

**Scope:** Task 3.3 / TASK-038.1 — database-at-rest encryption for the local-first SQLite path.
**Binding:** `sqlcipher3-wheels` (SQLCipher 4.x compatible).
**Key derivation:** Argon2id → 256-bit raw SQLCipher key.

---

## Threat model

Encryption protects against the case where **someone obtains the database file** (stolen laptop, backup left on a USB drive, cloud-upload accident, forensic copy of the disk). It does **not** protect a running app from a user who already knows the master password or from malware running in the same user session.

What is protected:
- SQLCipher encrypts every database page with AES-256-CBC + HMAC-SHA-512 (SQLCipher 4 defaults).
- The raw 256-bit key is derived from the user's master password and never stored in plaintext.
- A public salt sidecar is stored next to the database; the salt alone is useless without the password.

What is **not** protected:
- Memory dumps of a running TaxFlow process (the key lives in memory while the app is open).
- The password itself if the user writes it on a sticky note.
- A compromised OS user account that can read keystrokes.

---

## Configuration

Set these environment variables or entries in the project root `.env`:

```dotenv
# Required to enable SQLCipher.
DATABASE_URL=sqlcipher:///./taxflow.db
TAXFLOW_DB_PASSWORD=your-strong-master-password

# Optional second factors.
TAXFLOW_DB_KEYFILE=C:\TaxFlow\taxflow.key
TAXFLOW_DB_KEYRING_TOKEN=generated-token-stored-in-os-keyring
```

Plain SQLite remains the default if `DATABASE_URL` starts with `sqlite:///`.
SQLCipher is only enabled for URLs starting with `sqlcipher:///`, so existing dev/test flows are unaffected.

---

## Key lifecycle

1. **Password** — the user's master password (the only mandatory secret).
2. **Salt** — a random 16-byte salt is generated on first use and stored in `<db>.salt` (Base64) next to the database.
3. **Keyfile** (optional) — a user-supplied file whose SHA3-256 hash is mixed into the key.
4. **Keyring token** (optional) — a token stored in the OS credential store; its SHA3-256 hash is mixed into the key.
5. **Derived key** — Argon2id(password, salt) mixed with optional factor hashes via HKDF-SHA3-256 → 32 bytes.
6. **SQLCipher raw key** — passed as `PRAGMA key = "x'<64-hex>'"` on every connection. The key stays in memory only.

The salt sidecar is considered **public**: it can be backed up with the database. An attacker who has the salt but not the password (or keyfile/keyring token) cannot derive the key.

---

## First-run / bootstrap behavior

When a user boots TaxFlow with a SQLCipher URL and a master password:

- `backend/local/sqlcipher_engine.py` creates the salt sidecar if it does not exist.
- The SQLAlchemy engine unlocks the database on every connection via a `connect` event listener.
- Alembic migrations run as normal; schema is created inside the encrypted file.

No separate "create encrypted database" step is required; simply set `DATABASE_URL=sqlcipher:///...` and start the app.

---

## Migrating an existing plain SQLite database

Use the helper:

```python
from pathlib import Path
from backend.local.sqlcipher_engine import migrate_plaintext_to_sqlcipher

migrate_plaintext_to_sqlcipher(
    Path("taxflow.db"),
    Path("taxflow-encrypted.db"),
    "your-strong-master-password",
    # optional:
    # keyfile_path=Path("taxflow.key"),
)
```

This leaves the original database untouched and writes a new encrypted copy.
After verifying the encrypted copy, delete or securely wipe the old plaintext file.

For rekeying (changing the password or optional factors):

```python
from backend.local.sqlcipher_engine import rekey_sqlcipher_database

rekey_sqlcipher_database(
    Path("taxflow-encrypted.db"),
    old_password="old",
    new_password="new",
)
```

---

## Backup considerations

An encrypted database backup is only useful if the same salt sidecar is available and the same password/keyfile/keyring token are supplied on restore. Backups therefore must copy **both** files:

- `<db>` (encrypted SQLite database)
- `<db>.salt` (public salt sidecar)

If a keyfile was used, it must be preserved separately.
If a keyring token was used, the same OS credential store entry must be present on the restore machine.

TASK-038.2 implements the backup/restore layer that handles these details.

---

## What Josh / btsinnovations must decide for production

The following are **not** hardcoded by this implementation because they are product/business decisions:

| Decision | Default in code | Open question |
|---|---|---|
| Should encryption be mandatory or opt-in? | Opt-in (plain SQLite default) | Single-user local app may default to encrypted once installer UX is ready. |
| Keyfile generation UX | Optional; caller provides path | Should the installer generate a keyfile? Should it live on a removable drive? |
| OS-keyring integration | Optional token factor | Which OS keyring backends are supported? Is keyring the default second factor? |
| Argon2id parameters | 3 iterations, 64 MiB, 1 lane | Higher cost increases boot time; lower cost weakens brute-force resistance. Pick target boot-time budget. |
| Password policy | Not enforced here; enforced by `backend/utils/password_policy.py` for auth passwords | Should DB master password share the same policy? |
| Encrypted database file extension | Same as URL path (e.g., `taxflow.db`) | Should encrypted files be named `.db` or `.sqlcipher` for user clarity? |
| Migration prompt | Manual helper | Should first launch detect a plaintext `taxflow.db` and offer in-place encryption? |

These defaults are intentionally conservative and can be changed via settings or the bootstrap wizard without altering the engine.

---

## Files

- `backend/local/sqlcipher_engine.py` — engine factory, key derivation, migration, rekey.
- `backend/database.py` — routes `sqlcipher:///` URLs to the SQLCipher engine.
- `backend/local/settings.py` — declares encryption-related environment variables.
- `backend/tests/test_sqlcipher_engine.py` — round-trip, migration, rekey, keyfile tests.

---

## Verification

```bash
python -m pytest backend/tests/test_sqlcipher_engine.py -v
```

Expected: **6 passed** (when `sqlcipher3-wheels` is installed).

Full regression:

```bash
python -m pytest backend/tests -q
```

Expected: all existing tests pass unchanged when `DATABASE_URL` is not `sqlcipher:///...`.
