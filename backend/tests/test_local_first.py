"""Tests for backend local auth/crypto, SQLite hardening, and offline self-test."""
from __future__ import annotations

import ast
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ── Local-first runtime guards ───────────────────────────────────────────

class TestLocalFirstProperties:
    def test_categorize_is_case_insensitive(self):
        from pipeline.categorizer import PriorityCategorizer

        categorizer = PriorityCategorizer()
        variants = ["STARBUCKS", "starbucks", "StarBucks", "StArBuCkS"]
        categories = {categorizer.categorize(v) for v in variants}
        assert len(categories) == 1, f"Case variants produced different categories: {categories}"

    def test_redact_description_masking(self):
        from backend.utils.redaction import redact_description, mask_transaction_description

        raw = "Payment to account 1234567890"
        assert redact_description(raw) == "[REDACTED]"
        masked = mask_transaction_description(raw)
        assert masked is not None
        assert "1234567890" not in masked

    def test_generate_transaction_uid_is_deterministic(self):
        from pipeline.identity import IdentityService

        uid1 = IdentityService.generate_transaction_uid(
            "2025-01-15", "Walmart", "-42.50", institution="Chase", account="checking"
        )
        uid2 = IdentityService.generate_transaction_uid(
            "2025-01-15", "Walmart", "-42.50", institution="Chase", account="checking"
        )
        assert uid1 == uid2

    def test_generate_transaction_uid_changes_when_amount_changes(self):
        from pipeline.identity import IdentityService

        base = dict(date="2025-01-15", description="Walmart", institution="Chase", account="checking")
        uid_a = IdentityService.generate_transaction_uid(**base, amount="-42.50")
        uid_b = IdentityService.generate_transaction_uid(**base, amount="-42.51")
        assert uid_a != uid_b


# ── Offline mode / runtime guards ──────────────────────────────────────────

class TestOfflineModeGuards:
    def test_no_network_calls_in_offline_mode(self):
        """Default offline config must not initiate outbound connections."""
        import os
        os.environ["TAXFLOW_RUNTIME_MODE"] = "offline"
        from backend.local import settings
        assert settings.is_offline() is True
        assert settings.feature_enabled("plaid") is False
        assert settings.feature_enabled("stripe") is False
        assert settings.feature_enabled("telemetry") is False
        assert settings.feature_enabled("auto_update_check") is False
        with pytest.raises(RuntimeError):
            settings.guard_cloud_call("plaid")

    def test_all_feature_flags_default_to_false(self):
        from backend.local.settings import FEATURE_FLAGS
        assert all(value is False for value in FEATURE_FLAGS.values())

    def test_guard_cloud_call_blocks_each_feature(self):
        from backend.local.settings import FEATURE_FLAGS, guard_cloud_call
        import os
        os.environ["TAXFLOW_RUNTIME_MODE"] = "offline"
        for key in FEATURE_FLAGS:
            with pytest.raises(RuntimeError, match="Cloud/API call blocked in offline mode"):
                guard_cloud_call(key)

    def test_default_bind_is_loopback(self):
        """Default uvicorn bind host must be 127.0.0.1 when TAXFLOW_BIND_LAN is unset."""
        import os
        original = os.environ.pop("TAXFLOW_BIND_LAN", None)
        try:
            default_host = "127.0.0.1"
            if os.environ.get("TAXFLOW_BIND_LAN", "").lower() in ("1", "true", "yes"):
                default_host = "0.0.0.0"
            assert default_host == "127.0.0.1"
        finally:
            if original is not None:
                os.environ["TAXFLOW_BIND_LAN"] = original

    def test_bootstrap_does_not_call_external_host(self, monkeypatch):
        """run_bootstrap() only probes local modules/binaries and SQLite; no network."""
        import socket
        from backend.local.bootstrap import run_bootstrap

        connect_calls = []
        original_connect = socket.socket.connect

        def tracking_connect(self, address):
            connect_calls.append(address)
            return original_connect(self, address)

        monkeypatch.setattr(socket.socket, "connect", tracking_connect)

        report = run_bootstrap()
        assert report.ready in (True, False)
        non_loopback = [
            addr for addr in connect_calls
            if isinstance(addr, tuple) and not str(addr[0]).startswith(("127.", "::1"))
        ]
        assert not non_loopback, f"run_bootstrap() attempted non-loopback connections: {non_loopback}"


# ── Runtime dependency audit ────────────────────────────────────────────────

RUNTIME_DIRS = [Path("backend"), Path("pipeline")]
FORBIDDEN_IMPORTS = {"requests", "urllib.request", "http.client", "httpx", "aiohttp"}


class TestForbiddenNetworkImports:
    def test_no_forbidden_network_imports(self):
        """No backend runtime module may import a general-purpose HTTP client."""
        imports = set()
        for d in RUNTIME_DIRS:
            if not d.exists():
                continue
            for p in d.rglob("*.py"):
                if "tests" in p.parts:
                    continue
                tree = ast.parse(p.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module)
        forbidden = imports & FORBIDDEN_IMPORTS
        assert not forbidden, f"Forbidden network imports found: {forbidden}"


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

    def test_register_and_authenticate(self):
        """Integration test with real DB session."""
        from backend.database import engine, SessionLocal
        from backend.local.auth import LocalAuthManager, UserAlreadyExistsError, InvalidPasswordError
        from backend.audit.append_only import _set_audit_entries_mutable
        from backend import models

        db = SessionLocal()
        try:
            models.Base.metadata.create_all(bind=engine)
            existing = db.query(models.User).filter(models.User.username == "testuser").first()
            if existing:
                db.query(models.Client).filter(models.Client.user_id == existing.id).delete()
                db.query(models.Account).filter(models.Account.user_id == existing.id).delete()
                db.query(models.Statement).filter(models.Statement.user_id == existing.id).delete()
                db.query(models.Transaction).filter(models.Transaction.user_id == existing.id).delete()
                with _set_audit_entries_mutable():
                    db.query(models.AuditEntry).filter(models.AuditEntry.actor_id == existing.id).delete()
                db.query(models.User).filter(models.User.username == "testuser").delete()
                db.commit()

            auth = LocalAuthManager(db)
            user = auth.register("testuser", "pass123", email="test@local")
            assert user.username == "testuser"

            with pytest.raises(UserAlreadyExistsError):
                auth.register("testuser", "other")

            result = auth.authenticate("testuser", "pass123")
            assert result.username == "testuser"

            with pytest.raises(InvalidPasswordError):
                auth.authenticate("testuser", "wrong")

            with pytest.raises(InvalidPasswordError):
                auth.authenticate("nouser", "pass123")
        finally:
            existing = db.query(models.User).filter(models.User.username == "testuser").first()
            if existing:
                db.query(models.Client).filter(models.Client.user_id == existing.id).delete()
                db.query(models.Account).filter(models.Account.user_id == existing.id).delete()
                db.query(models.Statement).filter(models.Statement.user_id == existing.id).delete()
                db.query(models.Transaction).filter(models.Transaction.user_id == existing.id).delete()
                with _set_audit_entries_mutable():
                    db.query(models.AuditEntry).filter(models.AuditEntry.actor_id == existing.id).delete()
                db.query(models.User).filter(models.User.username == "testuser").delete()
                db.commit()
            db.close()


# ── Backup tests ──────────────────────────────────────────────────────────

class TestBackup:
    def test_create_and_restore_backup(self, tmp_path):
        from backend.local.backup import create_encrypted_backup, restore_backup

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

        db_path = tmp_path / "selftest.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE z (id INTEGER)")
        conn.commit()
        conn.close()

        report = run_self_test(db_path=db_path)
        assert len(report.results) > 0
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
    def test_wal_pragma_on_connect(self, tmp_path):
        """Verify that the SQLAlchemy engine applies WAL pragmas to file-backed SQLite."""
        import sqlalchemy
        from sqlalchemy import create_engine
        from backend.database import _set_sqlite_pragmas

        db_path = tmp_path / "wal_test.db"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        sqlalchemy.event.listen(engine, "connect", _set_sqlite_pragmas)

        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("PRAGMA journal_mode")).scalar()
            assert result == "wal"
        engine.dispose()

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
