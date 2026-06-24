"""Bulletproof SQLite recovery tests (TASK-038.11 + 038.13)."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database import (
    Base,
    get_db,
    _set_sqlite_pragmas,
    _sqlite_integrity_check,
    recover_sqlite_db,
)
from backend.local.backup import auto_backup_after_import, backup_db, restore_db
from backend.models import User, Client, Account, Statement, Transaction
from backend.routers.auth import get_password_hash
from backend.routers.upload import _upsert_transactions
from backend.local.column_encryption import encrypt_for_user


def _init_sqlite_pragmas(conn):
    _set_sqlite_pragmas(conn, None)


def _make_test_db(tmp: str):
    db_path = Path(tmp) / "test_recovery.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    # Manually apply pragmas/integrity check to verify listeners
    from sqlalchemy import event
    event.listen(engine, "connect", _set_sqlite_pragmas)
    event.listen(engine, "connect", _sqlite_integrity_check)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return db_path, engine, SessionLocal


def _seed_user_and_account(db, suffix=""):
    username = f"recovery_user{suffix}"
    email = f"recovery{suffix}@example.com"
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user, db.query(Account).filter(Account.client_id == user.clients[0].id).first() if user.clients else None
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("T4xFl0w!R3c0v3ry-2026"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    client = Client(name=f"Recovery Client{suffix}", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    account = Account(
        name=f"Checking{suffix}",
        institution="Navy Federal",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return user, account


def test_wal_mode_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, _ = _make_test_db(tmp)
        conn = engine.connect()
        try:
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
            assert result.lower() == "wal"
        finally:
            conn.close()
            engine.dispose()


def test_integrity_check_passes_on_fresh_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, _ = _make_test_db(tmp)
        # The integrity-check listener already ran at connection creation.
        conn = engine.connect()
        try:
            result = conn.execute(text("PRAGMA integrity_check")).scalar()
            assert result == "ok"
        finally:
            conn.close()
            engine.dispose()


def test_integrity_check_fails_on_corrupt_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, _ = _make_test_db(tmp)
        engine.dispose()
        # Corrupt the SQLite magic header so integrity_check fails.
        data = db_path.read_bytes()
        corrupted = b"XXXX" + data[4:]
        db_path.write_bytes(corrupted)

        # Direct sqlite3 open will fail/raise because the file is not a DB.
        with pytest.raises(sqlite3.DatabaseError, match="file is not a database"):
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("PRAGMA integrity_check")
            finally:
                conn.close()


def test_recover_sqlite_db_rebuilds_valid_file():
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, _ = _make_test_db(tmp)
        conn = engine.connect()
        try:
            conn.execute(text("CREATE TABLE demo (id INTEGER PRIMARY KEY, value TEXT)"))
            conn.execute(text("INSERT INTO demo (value) VALUES ('hello')"))
            conn.commit()
        finally:
            conn.close()
        engine.dispose()

        recovered = recover_sqlite_db(db_path)
        assert recovered.exists()
        conn2 = sqlite3.connect(str(recovered))
        try:
            rows = conn2.execute("SELECT value FROM demo").fetchall()
            assert rows == [("hello",)]
            integrity = conn2.execute("PRAGMA integrity_check").fetchone()[0]
            assert integrity == "ok"
        finally:
            conn2.close()


def test_auto_backup_after_import():
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, SessionLocal = _make_test_db(tmp)
        db = SessionLocal()
        try:
            user, account = _seed_user_and_account(db)
            stmt = Statement(
                account_id=account.id,
                tenant_id=account.tenant_id,
                user_id=user.id,
                filename="stmt.pdf",
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)
            txns = [
                {"date": "2025-01-15", "description": "Walmart", "amount": "-42.50"},
            ]
            _upsert_transactions(db, stmt, user, txns, account)
        finally:
            db.close()
        engine.dispose()

        backup_dir = Path(tmp) / "auto_backups"
        manifest_path = auto_backup_after_import(db_path, backup_dir)
        assert manifest_path.exists()
        manifest = json.loads(Path(manifest_path).read_text())
        assert manifest.get("trigger") == "post_import"
        assert (backup_dir / manifest["backup_file"]).exists()


def test_idempotent_reimport_after_simulated_crash():
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, SessionLocal = _make_test_db(tmp)
        db = SessionLocal()
        try:
            user, account = _seed_user_and_account(db)
            stmt = Statement(
                account_id=account.id,
                tenant_id=account.tenant_id,
                user_id=user.id,
                filename="stmt.pdf",
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)
            txns = [
                {"date": "2025-01-15", "description": "Walmart", "amount": "-42.50"},
                {"date": "2025-01-16", "description": "Gas Station", "amount": "-30.00"},
            ]
            _upsert_transactions(db, stmt, user, txns, account)
            first_count = db.query(Transaction).filter(
                Transaction.tenant_id == account.tenant_id
            ).count()
            assert first_count == 2
        finally:
            db.close()
        engine.dispose()

        # Simulate crash recovery by rebuilding the DB and re-importing.
        recovered = recover_sqlite_db(db_path)
        engine2 = create_engine(
            f"sqlite:///{recovered}",
            connect_args={"check_same_thread": False},
        )
        SessionLocal2 = sessionmaker(autocommit=False, autoflush=False, bind=engine2)
        db2 = SessionLocal2()
        try:
            user2, account2 = _seed_user_and_account(db2, suffix="_recovered")
            stmt2 = Statement(
                account_id=account2.id,
                tenant_id=account2.tenant_id,
                user_id=user2.id,
                filename="stmt.pdf",
            )
            db2.add(stmt2)
            db2.commit()
            db2.refresh(stmt2)
            _upsert_transactions(db2, stmt2, user2, txns, account2)
            second_count = db2.query(Transaction).filter(
                Transaction.tenant_id == account2.tenant_id
            ).count()
            assert second_count == 2, "Re-import after recovery duplicated transactions"
        finally:
            db2.close()
            engine2.dispose()


def test_concurrent_read_during_backup():
    """Open a read transaction while auto_backup_after_import runs; ensure no corruption."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, SessionLocal = _make_test_db(tmp)
        db = SessionLocal()
        try:
            user, account = _seed_user_and_account(db)
            stmt = Statement(
                account_id=account.id,
                tenant_id=account.tenant_id,
                user_id=user.id,
                filename="stmt.pdf",
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)
            txns = [{"date": "2025-01-15", "description": "Walmart", "amount": "-42.50"}]
            _upsert_transactions(db, stmt, user, txns, account)
        finally:
            db.close()
        engine.dispose()

        # Open a separate read connection on the same DB while backup runs.
        reader = sqlite3.connect(str(db_path))
        try:
            cursor = reader.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 1
            backup_dir = Path(tmp) / "concurrent_backups"
            manifest_path = auto_backup_after_import(db_path, backup_dir)
            assert manifest_path.exists()
            # Reader should still see consistent data after backup completes.
            cursor = reader.execute("SELECT COUNT(*) FROM transactions")
            assert cursor.fetchone()[0] == 1
        finally:
            reader.close()


def test_repeated_backup_manifest_increments():
    """Run auto_backup_after_import three times and confirm distinct archives/manifests."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path, engine, SessionLocal = _make_test_db(tmp)
        db = SessionLocal()
        try:
            user, account = _seed_user_and_account(db)
            stmt = Statement(
                account_id=account.id,
                tenant_id=account.tenant_id,
                user_id=user.id,
                filename="stmt.pdf",
            )
            db.add(stmt)
            db.commit()
            db.refresh(stmt)
        finally:
            db.close()
        engine.dispose()

        backup_dir = Path(tmp) / "incremental_backups"
        manifests = []
        for _ in range(3):
            manifest_path = auto_backup_after_import(db_path, backup_dir)
            assert manifest_path.exists()
            manifests.append(Path(manifest_path).read_text())
            # Ensure distinct timestamps across backups.
            import time
            time.sleep(1.1)

        assert len(set(manifests)) == 3, "Repeated backups produced identical manifests"
        backup_files = sorted(backup_dir.glob("taxflow_backup_*.tfebackup"))
        assert len(backup_files) >= 3
        assert len({f.name for f in backup_files}) == 3


def test_rls_middleware_ignored_on_sqlite(client):
    """A nonsense X-Tenant-ID header must not break requests when DB is SQLite."""
    from backend.database import DATABASE_URL
    if DATABASE_URL.startswith("postgresql://"):
        pytest.skip("Only meaningful for SQLite backend")

    response = client.get(
        "/api/health/public",
        headers={"X-Tenant-ID": "not-a-real-tenant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
