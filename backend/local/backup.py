"""Local backup, restore, and snapshot utilities.

Backups of the TaxFlow database are encrypted with the current local secret
and stored as versioned archives in a user-controlled directory. SQLCipher
enabled databases are fully encrypted at rest; the backup simply copies the
encrypted bytes plus the public salt sidecar required to re-derive the key.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import hashlib
import tarfile
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .crypto import LocalCryptoManager
from backend.auth import get_local_secret
from backend.crypto.backup_crypto import (
    encrypt_backup_with_secret,
    decrypt_backup_with_secret,
    BackupCryptoError as _BackupCryptoError,
)


class BackupError(Exception):
    pass


def is_sqlcipher_database(path: Path) -> bool:
    """Return True if the given path appears to be an encrypted SQLCipher DB.

    This is a best-effort heuristic: we look for a salt sidecar (``.salt``)
    next to the database and confirm the file does NOT start with the normal
    SQLite magic header. A plain SQLite database without a salt sidecar is
    never flagged as SQLCipher, even if the header check happens to disagree.
    """
    path = Path(path)
    salt = _salt_path(path)
    if not salt.exists():
        return False
    if not path.exists():
        return True
    try:
        header = path.read_bytes()[:16]
    except Exception:
        return False
    return header != b"SQLite format 3\0"


def _salt_path(db_path: Path) -> Path:
    return Path(str(db_path) + ".salt")


def _copy_with_retries(src: Path, dst: Path, retries: int = 10) -> None:
    """Copy a file, retrying briefly if Windows keeps a lock on a SQLCipher DB."""
    for attempt in range(retries):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            import time
            time.sleep(0.05)


def _sqlcipher_backup_files(db_path: Path) -> tuple[Path, Optional[Path]]:
    """Return the database path and its optional salt sidecar path."""
    salt = _salt_path(db_path)
    return db_path, salt if salt.exists() else None


def _sqlcipher_restore_files(
    backup_dir: Path,
    db_name: str,
) -> tuple[Path, Optional[Path]]:
    """Return the expected DB backup file and optional salt backup file."""
    db_file = backup_dir / db_name
    salt_file = backup_dir / f"{db_name}.salt"
    return db_file, salt_file if salt_file.exists() else None



def create_encrypted_backup(
    db_path: Path,
    backup_dir: Path,
    crypto: Optional[LocalCryptoManager] = None,
    metadata: Optional[dict] = None,
) -> Path:
    """Create a timestamped, optionally encrypted backup archive of the database.

    The backup includes:
        - The SQLite database file
        - A manifest.json with timestamp, schema version, and optional metadata
    """
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"taxflow_backup_{timestamp}.tar.gz"
    archive_path = backup_dir / archive_name

    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "database_name": db_path.name,
        "schema_version": metadata.get("schema_version") if metadata else None,
        "encrypted": crypto is not None,
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Copy DB to temp for atomic snapshot
        snapshot_path = tmp_path / db_path.name
        shutil.copy2(db_path, snapshot_path)

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        if crypto:
            encrypted = crypto.encrypt(snapshot_path.read_bytes())
            snapshot_path.write_bytes(encrypted)

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(snapshot_path, arcname=snapshot_path.name)
            tar.add(manifest_path, arcname="manifest.json")

    return archive_path


def restore_backup(
    archive_path: Path,
    target_dir: Path,
    crypto: Optional[LocalCryptoManager] = None,
) -> Path:
    """Restore a backup archive to the target directory."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    def _safe_members(members):
        for member in members:
            member_path = Path(member.name)
            if member_path.is_absolute():
                continue
            resolved = (tmp_path / member_path).resolve()
            if not str(resolved).startswith(str(tmp_path.resolve())):
                continue
            yield member

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=tmp_path, members=_safe_members(tar.getmembers()))

        manifest_path = tmp_path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        db_name = manifest["database_name"]
        source_db = tmp_path / db_name

        if crypto:
            decrypted = crypto.decrypt(source_db.read_bytes())
            source_db.write_bytes(decrypted)

        target_db = target_dir / db_name
        shutil.copy2(source_db, target_db)
        return target_db


def enable_wal(db_path: Path) -> None:
    """Enable SQLite WAL mode for crash recovery and concurrent reads."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    finally:
        conn.close()


def integrity_check(db_path: Path) -> list:
    """Run SQLite integrity check and return any messages."""
    conn = sqlite3.connect(str(db_path))
    try:
        result = conn.execute("PRAGMA integrity_check").fetchall()
        return [row[0] for row in result]
    finally:
        conn.close()


def backup_db(
    db_path: str,
    target_dir: str,
    plaintext: bool = False,
    metadata: dict | None = None,
) -> Path:
    """Create a backup of a SQLite DB in ``target_dir``.

    By default the database bytes are encrypted with a key derived from the
    current local secret and written as a ``.tfebackup`` file. Pass
    ``plaintext=True`` for the legacy unencrypted format (deprecated).

    If the database is a SQLCipher database, the salt sidecar (``<db>.salt``)
    is copied into the backup directory alongside the encrypted backup so the
    backup can be restored on the same machine without re-deriving the salt.

    Optional ``metadata`` is merged into the manifest.

    Returns the path to the backup manifest JSON file.
    """
    db_path = Path(db_path)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    db_bytes = db_path.read_bytes()
    db_hash = hashlib.sha256(db_bytes).hexdigest()
    timestamp = datetime.now(timezone.utc).isoformat()

    if plaintext:
        warnings.warn(
            "Plaintext backups are deprecated and will be removed in a future release. "
            "Use the default encrypted format instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        backup_db_path = target_dir / db_path.name
        shutil.copy2(db_path, backup_db_path)

        manifest = {
            "timestamp_utc": timestamp,
            "database_name": db_path.name,
            "sha256": db_hash,
            "version": "3.9.1",
            "encrypted": False,
        }
    else:
        local_secret = get_local_secret()
        encrypted = encrypt_backup_with_secret(db_bytes, local_secret)

        backup_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = f"taxflow_backup_{backup_ts}.tfebackup"
        backup_db_path = target_dir / backup_name
        backup_db_path.write_bytes(encrypted)

        manifest = {
            "timestamp_utc": timestamp,
            "database_name": db_path.name,
            "backup_file": backup_name,
            "sha256": db_hash,
            "version": "3.9.2",
            "encrypted": True,
            "format_version": 1,
            "sqlcipher": is_sqlcipher_database(db_path),
        }

    if metadata:
        manifest.update(metadata)

    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Copy SQLCipher salt sidecar if present. The salt is public and required
    # to derive the key on the restore machine.
    salt_file = _salt_path(db_path)
    if salt_file.exists():
        _copy_with_retries(salt_file, target_dir / salt_file.name)

    return manifest_path




def restore_db(backup_dir: str, target_path: str, plaintext: bool = False) -> Path:
    """Restore a backup directory to a target database path after verifying hash.

    Encrypted backups are decrypted using the current local secret. Plaintext
    restores are still supported for one release but emit a deprecation
    warning.

    Raises BackupError if the manifest is missing, the backup cannot be
    decrypted, or the SHA-256 does not match.
    """
    backup_dir = Path(backup_dir)
    target_path = Path(target_path)
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise BackupError(f"Backup manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    db_name = manifest.get("database_name")
    if not db_name:
        raise BackupError("Backup manifest missing database_name")

    is_encrypted = bool(manifest.get("encrypted"))

    if is_encrypted:
        backup_file_name = manifest.get("backup_file") or db_name
        backup_file_path = backup_dir / backup_file_name
        if not backup_file_path.exists():
            raise BackupError(f"Encrypted backup file not found: {backup_file_path}")

        local_secret = get_local_secret()
        try:
            decrypted = decrypt_backup_with_secret(
                backup_file_path.read_bytes(), local_secret
            )
        except _BackupCryptoError as exc:
            raise BackupError(
                f"Backup decryption failed; local secret may have changed: {exc}"
            ) from exc
        actual_hash = hashlib.sha256(decrypted).hexdigest()
        db_bytes = decrypted
    else:
        warnings.warn(
            "Restoring a plaintext backup is deprecated and will be removed in a future release. "
            "Use encrypted backups for new archives.",
            DeprecationWarning,
            stacklevel=2,
        )
        backup_db_path = backup_dir / db_name
        if not backup_db_path.exists():
            raise BackupError(f"Backup database not found: {backup_db_path}")
        db_bytes = backup_db_path.read_bytes()
        actual_hash = hashlib.sha256(db_bytes).hexdigest()

    expected_hash = manifest.get("sha256")
    if not expected_hash:
        raise BackupError("Backup manifest missing sha256")
    if actual_hash != expected_hash:
        raise BackupError("Backup hash mismatch; backup may be tampered or corrupt")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(db_bytes)

    # Restore the SQLCipher salt sidecar if the manifest marks this as a
    # SQLCipher database and the backup directory contains the sidecar.
    if manifest.get("sqlcipher"):
        salt_file = _salt_path(target_path)
        backup_salt = backup_dir / (db_name + ".salt")
        if backup_salt.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            _copy_with_retries(backup_salt, salt_file)
    return target_path


# Aliases for callers that expect `restore_db` to return the target path.
def restore_database(backup_dir: str, target_path: str, plaintext: bool = False) -> Path:
    """Alias of ``restore_db`` with a clearer name."""
    return restore_db(backup_dir, target_path, plaintext=plaintext)


def backup_database(db_path: str, target_dir: str, plaintext: bool = False, **kwargs) -> Path:
    """Alias of ``backup_db`` with a clearer name."""
    return backup_db(db_path, target_dir, plaintext=plaintext, **kwargs)


def auto_backup_after_import(
    db_path: str | Path,
    backup_dir: str | Path | None = None,
    metadata: dict | None = None,
) -> Path:
    """Create an encrypted backup immediately after a successful import.

    This is the automatic backup hook called by the upload success path.
    It delegates to ``backup_db()`` and records the import timestamp in the
    manifest metadata.
    """
    db_path = Path(db_path)
    if backup_dir is None:
        backup_dir = Path("./backups/auto")
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    extra = {"trigger": "post_import"}
    if metadata:
        extra.update(metadata)
    return backup_db(str(db_path), str(backup_dir), metadata=extra)


