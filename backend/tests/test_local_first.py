"""Tests for backend local auth/crypto, SQLite hardening, and offline self-test."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ── Crypto tests ──────────────────────────────────────────────────────────

class TestLocalCrypto:
    def test_roundtrip_encrypt_decrypt(self):
        from backend.local.crypto import LocalCryptoManager

        manager = LocalCryptoManager.create("master-password")
        plaintext = b"sensitive tax data"
        ciphertext = manager.encrypt(plaintext)
        assert manager.decrypt(ciphertext) == plaintext

    def test_wrong_password_fails(self):
        from backend.local.crypto import LocalCryptoManager, AuthenticationError

        manager1 = LocalCryptoManager.create("correct-password")
        ciphertext = manager1.encrypt(b"secret")

        manager2 = LocalCryptoManager.create("wrong-password", salt=manager1._salt)
        with pytest.raises(AuthenticationError):
            manager2.decrypt(ciphertext)

    def test_keyfile_factor(self, tmp_path):
        from backend.local.crypto import LocalCryptoManager, generate_keyfile

        keyfile = generate_keyfile(tmp_path / "test.key")
        manager = LocalCryptoManager.create("password", keyfile)
        ct = manager.encrypt(b"double-protected")

        # Without keyfile, decryption should fail
        manager_no_key = LocalCryptoManager.create("password", salt=manager._salt)
        with pytest.raises(Exception):
            manager_no_key.decrypt(ct)

    def test_generate_keyfile(self, tmp_path):
        from backend.local.crypto import generate_keyfile

        path = generate_keyfile(tmp_path / "key.bin", size=64)
        assert path.exists()
        assert len(path.read_bytes()) == 64

    def test_from_stored_roundtrip(self):
        from backend.local.crypto import LocalCryptoManager

        original = LocalCryptoManager.create("password123")
        salt_b64 = original.salt_b64
        ct = original.encrypt(b"data")

        restored = LocalCryptoManager.from_stored("password123", salt_b64)
        assert restored.decrypt(ct) == b"data"

    def test_envelope_version_check(self):
        from backend.local.crypto import LocalCryptoManager, EncryptionError

        manager = LocalCryptoManager.create("pw")
        with pytest.raises(EncryptionError, match="Unsupported envelope version"):
            manager.decrypt(b'{"v": 999, "salt_b64": "", "nonce_b64": "", "ciphertext_b64": ""}')


# ── Auth tests ────────────────────────────────────────────────────────────

class TestLocalAuth:
    def test_hash_and_verify_password(self):
        from backend.local.auth import LocalAuthManager

        stored = LocalAuthManager.hash_password("mypassword")
        assert LocalAuthManager.verify_password("mypassword", stored) is True
        assert LocalAuthManager.verify_password("wrongpassword", stored) is False

    def test_register_and_authenticate(self, tmp_path):
        """Integration test with real DB session."""
        from backend.database import engine, SessionLocal
        from backend.local.auth import LocalAuthManager, UserAlreadyExistsError, InvalidPasswordError
        from backend import models

        db = SessionLocal()
        try:
            # Ensure tables exist
            models.Base.metadata.create_all(bind=engine)

            # Clean up any leftover test user
            db.query(models.User).filter(models.User.username == "testuser").delete()
            db.commit()

            auth = LocalAuthManager(db)
            user = auth.register("testuser", "pass123", email="test@local")
            assert user.username == "testuser"

            # Duplicate should fail
            with pytest.raises(UserAlreadyExistsError):
                auth.register("testuser", "other")

            # Correct password
            result = auth.authenticate("testuser", "pass123")
            assert result.username == "testuser"

            # Wrong password
            with pytest.raises(InvalidPasswordError):
                auth.authenticate("testuser", "wrong")

            # Non-existent user
            with pytest.raises(InvalidPasswordError):
                auth.authenticate("nouser", "pass123")
        finally:
            # Clean up
            db.query(models.User).filter(models.User.username == "testuser").delete()
            db.commit()
            db.close()


# ── Backup tests ──────────────────────────────────────────────────────────

class TestBackup:
    def test_create_and_restore_backup(self, tmp_path):
        from backend.local.backup import create_encrypted_backup, restore_backup

        # Create a small test SQLite database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        backup_dir = tmp_path / "backups"
        archive = create_encrypted_backup(db_path, backup_dir)
        assert archive.exists()

        restore_dir = tmp_path / "restored"
        restored_db = restore_backup(archive, restore_dir)
        assert restored_db.exists()

        conn2 = sqlite3.connect(str(restored_db))
        row = conn2.execute("SELECT val FROM test WHERE id=1").fetchone()
        conn2.close()
        assert row[0] == "hello"

    def test_encrypted_backup(self, tmp_path):
        from backend.local.backup import create_encrypted_backup, restore_backup
        from backend.local.crypto import LocalCryptoManager

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        crypto = LocalCryptoManager.create("backup-password")
        archive = create_encrypted_backup(db_path, tmp_path / "bkp", crypto=crypto)
        assert archive.exists()

        restored = restore_backup(archive, tmp_path / "out", crypto=crypto)
        assert restored.exists()

    def test_wal_mode(self, tmp_path):
        from backend.local.backup import enable_wal

        db_path = tmp_path / "wal_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE x (id INTEGER)")
        conn.commit()
        conn.close()

        enable_wal(db_path)
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_integrity_check(self, tmp_path):
        from backend.local.backup import integrity_check

        db_path = tmp_path / "check.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE y (id INTEGER)")
        conn.commit()
        conn.close()

        results = integrity_check(db_path)
        assert results == ["ok"]


# ── Offline self-test ─────────────────────────────────────────────────────

class TestOfflineSelfTest:
    def test_self_test_runs(self, tmp_path):
        from backend.local.offline import run_self_test

        # Create a temp DB so the test has something to check
        db_path = tmp_path / "selftest.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE z (id INTEGER)")
        conn.commit()
        conn.close()

        report = run_self_test(db_path=db_path)
        assert len(report.results) > 0
        # Crypto round-trip should pass
        crypto_results = [r for r in report.results if r.name == "crypto:roundtrip"]
        assert len(crypto_results) == 1
        assert crypto_results[0].passed

    def test_report_to_dict(self, tmp_path):
        from backend.local.offline import run_self_test

        db_path = tmp_path / "dict_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.commit()
        conn.close()

        report = run_self_test(db_path=db_path)
        d = report.to_dict()
        assert "all_passed" in d
        assert "results" in d


# ── SQLite hardening (database.py) ────────────────────────────────────────

class TestSQLiteHardening:
    def test_wal_pragma_on_connect(self):
        """Verify that the SQLAlchemy engine applies WAL pragmas."""
        import sqlalchemy
        from backend.database import engine, DATABASE_URL

        if not DATABASE_URL.startswith("sqlite"):
            pytest.skip("Not using SQLite")

        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("PRAGMA journal_mode")).scalar()
            assert result == "wal"

    def test_foreign_keys_enabled(self):
        from backend.database import engine, DATABASE_URL

        if not DATABASE_URL.startswith("sqlite"):
            pytest.skip("Not using SQLite")

        import sqlalchemy
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("PRAGMA foreign_keys")).scalar()
            assert result == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])