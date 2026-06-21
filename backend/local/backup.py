"""Local backup, restore, and snapshot utilities.

All backups are encrypted (when crypto manager is provided) and stored as
versioned archives in a user-controlled directory.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .crypto import LocalCryptoManager


class BackupError(Exception):
    pass


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

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=tmp_path)

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
