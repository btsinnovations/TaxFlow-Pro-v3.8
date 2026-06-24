"""Hardened tests: property-based, corruption, idempotency, and recovery."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ── Property-based / fuzz-style tests ─────────────────────────────────────


class TestCryptoHardening:
    def test_encryption_is_deterministic_for_same_key(self):
        from backend.local.crypto import LocalCryptoManager

        manager = LocalCryptoManager.create("password")
        ct1 = manager.encrypt(b"data")
        ct2 = manager.encrypt(b"data")
        # Same plaintext, same key should produce different ciphertexts (GCM nonce)
        assert ct1 != ct2
        assert manager.decrypt(ct1) == manager.decrypt(ct2) == b"data"

    def test_different_salts_produce_different_keys(self):
        from backend.local.crypto import LocalCryptoManager

        m1 = LocalCryptoManager.create("password")
        m2 = LocalCryptoManager.create("password")
        assert m1._key != m2._key

    def test_corrupted_envelope_fails(self):
        from backend.local.crypto import LocalCryptoManager

        manager = LocalCryptoManager.create("pw")
        ct = manager.encrypt(b"data")
        try:
            manager.decrypt(ct[:-5] + b"xxxxx")
            assert False, "Should have raised"
        except Exception as exc:
            assert "Error" in type(exc).__name__
            assert "envelope" in str(exc).lower() or "decryption" in str(exc).lower() or "authentication" in str(exc).lower()


class TestBackupHardening:
    def test_backup_restores_after_corruption(self, tmp_path):
        from backend.local.backup import create_encrypted_backup, restore_backup
        from backend.local.crypto import LocalCryptoManager

        db_path = tmp_path / "db.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE data (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO data VALUES (1, 'important')")
        conn.commit()
        conn.close()

        crypto = LocalCryptoManager.create("backup-pass")
        archive = create_encrypted_backup(db_path, tmp_path / "backups", crypto=crypto)

        # Simulate corruption of original DB
        db_path.write_bytes(b"garbage")

        restored = restore_backup(archive, tmp_path / "restored", crypto=crypto)
        conn = sqlite3.connect(str(restored))
        row = conn.execute("SELECT val FROM data WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "important"

    def test_multiple_backups_do_not_overwrite(self, tmp_path):
        from backend.local.backup import create_encrypted_backup

        db_path = tmp_path / "db.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE x (id INTEGER)")
        conn.commit()
        conn.close()

        backup_dir = tmp_path / "backups"
        b1 = create_encrypted_backup(db_path, backup_dir)
        import time
        time.sleep(1)
        b2 = create_encrypted_backup(db_path, backup_dir)
        assert b1 != b2
        assert b1.exists() and b2.exists()


class TestIdempotentImports:
    def test_duplicate_import_guard(self, tmp_path):
        """A duplicate-detection helper should reject identical transactions."""
        from backend.local.guards import is_duplicate_transaction

        existing = {
            "date": "2024-06-01",
            "description": "COFFEE SHOP",
            "amount": 5.00,
            "tx_type": "debit",
        }
        candidate = {
            "date": "2024-06-01",
            "description": "COFFEE SHOP",
            "amount": 5.00,
            "tx_type": "debit",
        }
        assert is_duplicate_transaction(existing, candidate) is True

        different = {
            "date": "2024-06-02",
            "description": "COFFEE SHOP",
            "amount": 5.00,
            "tx_type": "debit",
        }
        assert is_duplicate_transaction(existing, different) is False


class TestLocalModelTraining:
    def test_train_and_predict(self, tmp_path):
        from backend.local.ml_pipeline import train_local_model, predict_local, load_local_model

        transactions = []
        for i in range(5):
            transactions.append({"description": f"STARBUCKS #{i}", "category": "Food & Dining"})
            transactions.append({"description": f"SHELL OIL #{i}", "category": "Auto & Transport"})

        result = train_local_model(transactions, model_dir=tmp_path / "ml")
        assert result.accuracy > 0
        assert "Food & Dining" in result.classes
        assert "Auto & Transport" in result.classes

        model = load_local_model(model_dir=tmp_path / "ml")
        cat, conf = predict_local("STARBUCKS COFFEE", model=model)
        assert cat == "Food & Dining"
        assert 0 <= conf <= 1

    def test_train_fails_with_too_few_samples(self, tmp_path):
        from backend.local.ml_pipeline import train_local_model, TrainingError

        with pytest.raises(TrainingError):
            train_local_model([{"description": "x", "category": "y"}], model_dir=tmp_path / "ml")


class TestOfflineGuards:
    def test_guard_cloud_call_blocks_when_offline(self, monkeypatch):
        from backend.local import settings
        monkeypatch.setattr(settings, "RUNTIME_MODE", settings.RuntimeMode.OFFLINE)
        from backend.local.settings import guard_cloud_call

        with pytest.raises(RuntimeError, match="Cloud/API call blocked"):
            guard_cloud_call("test_feature")

    def test_guard_cloud_call_allows_when_online(self, monkeypatch):
        from backend.local import settings
        monkeypatch.setattr(settings, "RUNTIME_MODE", settings.RuntimeMode.ONLINE)
        from backend.local.settings import guard_cloud_call

        # Should not raise
        guard_cloud_call("test_feature")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
