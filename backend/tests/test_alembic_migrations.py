"""Alembic migration health tests for v3.11 baseline."""

import gc
import os
import shutil
import tempfile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


def _make_cfg(db_path: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _run_upgrade(db_path: str) -> None:
    cfg = _make_cfg(db_path)
    command.upgrade(cfg, "head")


def _run_downgrade_to_pre_baseline(db_path: str) -> None:
    """Downgrade to the revision before v3.11 baseline/OFX columns were added.

    We intentionally do not downgrade to base because earlier v3.8/v3.9 migrations
    contain destructive downgrades that are not safe to exercise in a roundtrip test.
    """
    cfg = _make_cfg(db_path)
    command.downgrade(cfg, "ba949088fd32")


def _cleanup_dir(path: str) -> None:
    """Best-effort cleanup; ignore Windows file-lock races from Alembic."""
    for _ in range(3):
        gc.collect()
        try:
            shutil.rmtree(path, ignore_errors=True)
            return
        except PermissionError:
            pass


@pytest.fixture
def fresh_v3_11_db():
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "v3_11.db")
        _run_upgrade(db_path)
        yield db_path
    finally:
        _cleanup_dir(tmp)


@pytest.fixture
def v3_10_style_db():
    """Simulate a v3.10 DB with core tables before the v3.11 baseline migration."""
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "v3_10.db")
        engine = create_engine(f"sqlite:///{db_path}", poolclass=NullPool)
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    email TEXT,
                    hashed_password TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE clients (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    tax_id TEXT,
                    user_id INTEGER NOT NULL,
                    created_at TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE gl_accounts (
                    id INTEGER PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    account_type TEXT DEFAULT 'expense',
                    created_at TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE accounts (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    institution TEXT,
                    account_number_masked TEXT,
                    type TEXT DEFAULT 'checking',
                    client_id INTEGER NOT NULL,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE statements (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    filename TEXT,
                    period_start TEXT,
                    period_end TEXT,
                    opening_balance REAL,
                    closing_balance REAL,
                    created_at TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY,
                    statement_id INTEGER NOT NULL,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    gl_account_id INTEGER,
                    date TEXT,
                    description TEXT,
                    amount REAL,
                    tx_type TEXT,
                    category TEXT DEFAULT 'uncategorized',
                    running_balance REAL,
                    created_at TEXT
                )
            """))
        engine.dispose()
        cfg = _make_cfg(db_path)
        command.stamp(cfg, "ba949088fd32")
        yield db_path
    finally:
        _cleanup_dir(tmp)


def test_upgrade_from_v3_10_db(v3_10_style_db):
    _run_upgrade(v3_10_style_db)
    engine = create_engine(f"sqlite:///{v3_10_style_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "transactions" in tables
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "fitid" in cols
    finally:
        engine.dispose()


def test_upgrade_downgrade_roundtrip(fresh_v3_11_db):
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "fitid" in cols
        with engine.connect() as conn:
            gl_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(gl_accounts)"))}
        assert "is_active" in gl_cols
    finally:
        engine.dispose()

    _run_downgrade_to_pre_baseline(fresh_v3_11_db)

    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "fitid" not in cols
        with engine.connect() as conn:
            gl_cols = {r[1] for r in conn.execute(text("PRAGMA table_info(gl_accounts)"))}
        assert "is_active" not in gl_cols
    finally:
        engine.dispose()
