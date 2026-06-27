"""Alembic migration health tests for v3.11 and v3.11.6 baseline."""

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


def _run_downgrade_to_pre_coa(db_path: str) -> None:
    """Downgrade to the v3.11 baseline (before v3.11.6 COA migration)."""
    cfg = _make_cfg(db_path)
    command.downgrade(cfg, "330eb386b9c2")


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


# ---------------------------------------------------------------------------
# v3.11.6 COA migration tests
# ---------------------------------------------------------------------------


def test_v3_11_6_creates_coa_accounts_table(fresh_v3_11_db):
    """The v3.11.6 migration creates the coa_accounts table."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "coa_accounts" in tables

        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(coa_accounts)"))}
        assert "id" in cols
        assert "tenant_id" in cols
        assert "parent_id" in cols
        assert "number" in cols
        assert "name" in cols
        assert "type" in cols
        assert "is_active" in cols
        assert "created_at" in cols
        assert "updated_at" in cols
    finally:
        engine.dispose()


def test_v3_11_6_creates_missing_v3_11_tables(fresh_v3_11_db):
    """The v3.11.6 migration creates all missing v3.11 tables."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        expected = [
            "profile_memberships",
            "loan_schedules",
            "investment_lots",
            "inventory_items",
            "inventory_transactions",
            "fx_rates",
            "reconciliation_imports",
            "reconciliation_matches",
            "budget_lines",
            "recurring_rules",
            "tax_line_mappings",
        ]
        for tbl in expected:
            assert tbl in tables, f"Missing table: {tbl}"
    finally:
        engine.dispose()


def test_v3_11_6_adds_coa_account_id_to_transactions(fresh_v3_11_db):
    """The migration adds coa_account_id to transactions."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "coa_account_id" in cols
    finally:
        engine.dispose()


def test_v3_11_6_adds_coa_account_id_to_general_ledger_entries(fresh_v3_11_db):
    """The migration adds debit/credit coa_account_id to general_ledger_entries."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(general_ledger_entries)"))}
        assert "debit_coa_account_id" in cols
        assert "credit_coa_account_id" in cols
    finally:
        engine.dispose()


def test_v3_11_6_adds_coa_account_id_to_categorization_rules(fresh_v3_11_db):
    """The migration adds coa_account_id to categorization_rules."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(categorization_rules)"))}
        assert "coa_account_id" in cols
    finally:
        engine.dispose()


def test_v3_11_6_coa_accounts_unique_tenant_number(fresh_v3_11_db):
    """coa_accounts has a unique index on (tenant_id, number)."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            indexes = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='coa_accounts'"
            )).fetchall()
        index_names = {r[0] for r in indexes}
        assert "ix_coa_accounts_tenant_number" in index_names
    finally:
        engine.dispose()


def test_v3_11_6_migrates_gl_accounts_data(v3_10_style_db):
    """The migration copies gl_accounts data into coa_accounts."""
    # Seed some gl_accounts data before upgrading
    engine = create_engine(f"sqlite:///{v3_10_style_db}", poolclass=NullPool)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO clients (id, name, user_id) VALUES (1, 'Test Tenant', 1)"
        ))
        conn.execute(text(
            "INSERT INTO gl_accounts (id, tenant_id, user_id, code, name, account_type) "
            "VALUES (1, 1, 1, '1000', 'Cash', 'asset')"
        ))
        conn.execute(text(
            "INSERT INTO gl_accounts (id, tenant_id, user_id, code, name, account_type) "
            "VALUES (2, 1, 1, '5000', 'Office Supplies', 'expense')"
        ))
    engine.dispose()

    # Run the full upgrade (v3.11 baseline + v3.11.6 COA)
    _run_upgrade(v3_10_style_db)

    engine = create_engine(f"sqlite:///{v3_10_style_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT number, name, type FROM coa_accounts ORDER BY number"
            )).fetchall()
        assert len(rows) >= 2
        # The migration should have copied the data with integer numbers
        numbers = {r[0] for r in rows}
        assert 1000 in numbers
        assert 5000 in numbers
    finally:
        engine.dispose()


def test_v3_11_6_downgrade_roundtrip(fresh_v3_11_db):
    """Upgrade then downgrade back to v3.11 baseline preserves existing data."""
    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            tables_before = {r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ))}
        assert "coa_accounts" in tables_before
    finally:
        engine.dispose()

    # Downgrade to v3.11 baseline (before COA migration)
    _run_downgrade_to_pre_coa(fresh_v3_11_db)

    engine = create_engine(f"sqlite:///{fresh_v3_11_db}", poolclass=NullPool)
    try:
        with engine.connect() as conn:
            tables_after = {r[0] for r in conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ))}
        assert "coa_accounts" not in tables_after

        # Core v3.11 tables should still be present
        assert "transactions" in tables_after
        assert "gl_accounts" in tables_after
        assert "accounts" in tables_after

        # coa_account_id column should be gone from transactions
        with engine.connect() as conn:
            cols = {r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))}
        assert "coa_account_id" not in cols
    finally:
        engine.dispose()