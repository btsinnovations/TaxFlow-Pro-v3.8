"""Tests for DATA-01 backup/restore CLI helpers."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.local.backup import (
    BackupError,
    backup_db,
    is_sqlcipher_database,
    restore_db,
)
from backend.crypto.backup_crypto import (
    encrypt_backup_with_secret,
    decrypt_backup_with_secret,
    _decode_header,
)
from backend.local.sqlcipher_engine import (
    create_sqlcipher_engine,
    is_sqlcipher_available,
)


def _init_sqlite(path: Path):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO test_data (value) VALUES ('hello')")
    conn.commit()
    conn.close()


def test_backup_creates_encrypted_manifest_and_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "taxflow.db"
        target_dir = Path(tmp) / "backups"
        _init_sqlite(db_path)

        manifest_path = backup_db(str(db_path), str(target_dir))

        assert manifest_path.exists()
        manifest = _read_json(manifest_path)
        assert manifest["database_name"] == "taxflow.db"
        assert manifest["sha256"] == _sha256(db_path)
        assert manifest["version"] == "3.9.2"
        assert manifest["encrypted"] is True
        assert manifest["format_version"] == 1
        assert manifest.get("sqlcipher") in (False, None)
        assert "backup_file" in manifest

        backup_file = target_dir / manifest["backup_file"]
        assert backup_file.exists()

        version, salt, ciphertext = _decode_header(backup_file.read_bytes())
        assert version == 1
        assert len(salt) == 32
        assert ciphertext

        restored_path = Path(tmp) / "restored.db"
        result = restore_db(str(target_dir), str(restored_path))
        assert Path(result) == restored_path
        assert restored_path.exists()
        assert _sha256(restored_path) == _sha256(db_path)

        conn = sqlite3.connect(str(restored_path))
        try:
            rows = conn.execute("SELECT value FROM test_data").fetchall()
            assert rows == [("hello",)]
        finally:
            conn.close()


def test_restore_fails_when_local_secret_changes():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "taxflow.db"
        target_dir = Path(tmp) / "backups"
        _init_sqlite(db_path)

        backup_db(str(db_path), str(target_dir))

        # Simulate secret regeneration by overriding the secret used for restore.
        original_secret = os.environ.pop("TAXFLOW_SECRET_KEY", None)
        os.environ["TAXFLOW_SECRET_KEY"] = "a-different-secret-that-breaks-decryption"

        restored_path = Path(tmp) / "restored.db"
        try:
            with pytest.raises(BackupError, match="decryption failed"):
                restore_db(str(target_dir), str(restored_path))
        finally:
            if original_secret is not None:
                os.environ["TAXFLOW_SECRET_KEY"] = original_secret
            else:
                os.environ.pop("TAXFLOW_SECRET_KEY", None)


def test_plaintext_backup_and_restore_still_work():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "taxflow.db"
        target_dir = Path(tmp) / "backups"
        _init_sqlite(db_path)

        with pytest.warns(DeprecationWarning, match="Plaintext backups"):
            manifest_path = backup_db(str(db_path), str(target_dir), plaintext=True)

        manifest = _read_json(manifest_path)
        assert manifest["encrypted"] is False
        assert (target_dir / "taxflow.db").exists()

        with pytest.warns(DeprecationWarning, match="Restoring a plaintext backup"):
            restored_path = Path(tmp) / "restored.db"
            result = restore_db(str(target_dir), str(restored_path), plaintext=True)

        assert Path(result) == restored_path
        assert _sha256(restored_path) == _sha256(db_path)


def test_restore_with_tampered_encrypted_backup_fails():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "taxflow.db"
        target_dir = Path(tmp) / "backups"
        _init_sqlite(db_path)

        backup_db(str(db_path), str(target_dir))
        manifest = _read_json(target_dir / "manifest.json")
        backup_file = target_dir / manifest["backup_file"]

        # Corrupt the ciphertext after the header.
        data = bytearray(backup_file.read_bytes())
        data[-1] ^= 0xFF
        backup_file.write_bytes(bytes(data))

        restored_path = Path(tmp) / "restored.db"
        with pytest.raises(BackupError, match="decryption failed"):
            restore_db(str(target_dir), str(restored_path))


def test_restore_with_tampered_plaintext_backup_fails():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "taxflow.db"
        target_dir = Path(tmp) / "backups"
        _init_sqlite(db_path)

        with pytest.warns(DeprecationWarning):
            backup_db(str(db_path), str(target_dir), plaintext=True)

        # Tamper with the backup database file.
        backup_db_path = target_dir / "taxflow.db"
        conn = sqlite3.connect(str(backup_db_path))
        conn.execute("INSERT INTO test_data (value) VALUES ('tamper')")
        conn.commit()
        conn.close()

        restored_path = Path(tmp) / "restored.db"
        with pytest.raises(BackupError, match="hash mismatch"):
            restore_db(str(target_dir), str(restored_path), plaintext=True)


def test_crypto_helpers_round_trip():
    secret = "local-secret-for-derivation"
    plaintext = b"TaxFlow backup payload"
    ciphertext = encrypt_backup_with_secret(plaintext, secret)
    assert ciphertext.startswith(b"TFBU")
    assert decrypt_backup_with_secret(ciphertext, secret) == plaintext


def test_crypto_helpers_fail_with_wrong_secret():
    secret = "local-secret-for-derivation"
    plaintext = b"TaxFlow backup payload"
    ciphertext = encrypt_backup_with_secret(plaintext, secret)
    with pytest.raises(Exception, match="decryption failed"):
        decrypt_backup_with_secret(ciphertext, "wrong-secret")


@pytest.mark.skipif(not is_sqlcipher_available(), reason="sqlcipher3 not installed")
def test_is_sqlcipher_database_heuristic():
    # Plain SQLite starts with the SQLite magic header.
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "plain.db"
        _init_sqlite(plain)
        assert is_sqlcipher_database(plain) is False

    # Encrypted DB + salt sidecar should be detected.
    with tempfile.TemporaryDirectory() as tmp:
        enc = Path(tmp) / "enc.db"
        engine = create_sqlcipher_engine("sqlite:///" + str(enc), "testpass")
        Base = declarative_base()

        class _Note(Base):
            __tablename__ = "notes"
            id = Column(Integer, primary_key=True)
            text = Column(String)

        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        s = Session()
        s.add(_Note(text="note"))
        s.commit()
        s.close()
        engine.dispose()
        # Allow sqlcipher to release the Windows file lock.
        time.sleep(0.1)
        assert is_sqlcipher_database(enc) is True


@pytest.mark.skipif(not is_sqlcipher_available(), reason="sqlcipher3 not installed")
def test_sqlcipher_backup_and_restore_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        db = tmp / "taxflow.db"
        password = "SQLCipher-Backup-Test!"
        engine = create_sqlcipher_engine("sqlite:///" + str(db), password)
        Base = declarative_base()

        class _Note(Base):
            __tablename__ = "notes"
            id = Column(Integer, primary_key=True)
            text = Column(String)

        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        s = Session()
        s.add(_Note(text="restore-me"))
        s.commit()
        s.close()
        engine.dispose()
        # Give Windows time to release the native file handle.
        time.sleep(0.1)

        backup_dir = tmp / "backups"
        manifest_path = backup_db(str(db), str(backup_dir))
        manifest = _read_json(manifest_path)
        assert manifest.get("sqlcipher") is True
        assert (backup_dir / "taxflow.db.salt").exists()

        restored = tmp / "restored.db"
        restore_db(str(backup_dir), str(restored))
        assert is_sqlcipher_database(restored) is True
        assert (tmp / "restored.db.salt").exists()

        engine2 = create_sqlcipher_engine("sqlite:///" + str(restored), password)
        Session2 = sessionmaker(bind=engine2)
        s2 = Session2()
        assert s2.query(_Note).first().text == "restore-me"
        s2.close()
        engine2.dispose()


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    import json
    return json.loads(path.read_text())
