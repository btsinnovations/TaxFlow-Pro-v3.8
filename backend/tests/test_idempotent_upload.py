"""Idempotent transaction import tests for TaxFlow Pro v3.9."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, DATABASE_URL
from backend.models import Client, Account, Statement, Transaction, User
from backend.routers.auth import get_password_hash
from backend.routers.upload import _upsert_transactions
from phase3_pipeline.identity import IdentityService


def _make_test_db():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def _seed_user_and_account(db):
    user = User(
        username="idempotent_user",
        email="idempotent@example.com",
        hashed_password=get_password_hash("T4xFl0…2026"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    client = Client(name="Idempotent Client", user_id=user.id)
    db.add(client)
    db.commit()
    db.refresh(client)
    account = Account(
        name="Checking",
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


def _statement(db, account, user):
    stmt = Statement(
        account_id=account.id,
        tenant_id=account.tenant_id,
        user_id=user.id,
        filename="stmt1.pdf",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
    )
    db.add(stmt)
    db.commit()
    db.refresh(stmt)
    return stmt


def test_identity_transaction_uid_is_deterministic():
    uid1 = IdentityService.generate_transaction_uid(
        date="2025-01-15", description="WAL-MART #1234", amount=Decimal("42.50"),
        institution="Navy Federal", account="Checking",
    )
    uid2 = IdentityService.generate_transaction_uid(
        date="2025-01-15", description="WALMART", amount="$42.50",
        institution="navy federal", account="checking",
    )
    assert uid1 == uid2


def test_identity_transaction_uid_distinguishes_inputs():
    base = {
        "date": "2025-01-15",
        "description": "Walmart",
        "amount": Decimal("42.50"),
        "institution": "Navy Federal",
        "account": "Checking",
    }
    uids = {
        IdentityService.generate_transaction_uid(**{**base, "amount": Decimal("42.51")}),
        IdentityService.generate_transaction_uid(**{**base, "date": "2025-01-16"}),
        IdentityService.generate_transaction_uid(**{**base, "description": "Target"}),
        IdentityService.generate_transaction_uid(**{**base, "account": "Savings"}),
    }
    assert len(uids) == 4


def test_upsert_creates_transactions_on_first_import():
    engine, SessionLocal = _make_test_db()
    db = SessionLocal()
    try:
        user, account = _seed_user_and_account(db)
        stmt = _statement(db, account, user)
        txns = [
            {"date": "2025-01-15", "description": "Walmart", "amount": "-42.50", "running_balance": "957.50"},
            {"date": "2025-01-16", "description": "Gas Station", "amount": "-30.00", "running_balance": "927.50"},
        ]
        _upsert_transactions(db, stmt, user, txns, account)

        rows = db.query(Transaction).filter(Transaction.tenant_id == account.tenant_id).all()
        assert len(rows) == 2
        assert all(t.txn_uid is not None for t in rows)
        assert all(t.import_source == "upload" for t in rows)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_upsert_does_not_duplicate_on_reimport():
    engine, SessionLocal = _make_test_db()
    db = SessionLocal()
    try:
        user, account = _seed_user_and_account(db)
        stmt1 = _statement(db, account, user)
        txns = [
            {"date": "2025-01-15", "description": "Walmart", "amount": "-42.50", "running_balance": "957.50"},
        ]
        _upsert_transactions(db, stmt1, user, txns, account)
        first_count = db.query(Transaction).filter(Transaction.tenant_id == account.tenant_id).count()
        assert first_count == 1

        stmt2 = _statement(db, account, user)
        _upsert_transactions(db, stmt2, user, txns, account)
        second_count = db.query(Transaction).filter(Transaction.tenant_id == account.tenant_id).count()
        assert second_count == 1, "Re-import duplicated the transaction"

        row = db.query(Transaction).filter(Transaction.tenant_id == account.tenant_id).one()
        assert row.statement_id == stmt2.id
        assert row.import_source == "upload_upsert"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_upsert_updates_amount_on_changed_source_row():
    engine, SessionLocal = _make_test_db()
    db = SessionLocal()
    try:
        user, account = _seed_user_and_account(db)
        stmt1 = _statement(db, account, user)
        txns1 = [
            {"date": "2025-01-15", "description": "Walmart", "amount": "-42.50", "running_balance": "957.50"},
        ]
        _upsert_transactions(db, stmt1, user, txns1, account)

        stmt2 = _statement(db, account, user)
        txns2 = [
            {"date": "2025-01-16", "description": "Walmart", "amount": "-142.50", "running_balance": "857.50"},
        ]
        _upsert_transactions(db, stmt2, user, txns2, account)

        rows = db.query(Transaction).filter(Transaction.tenant_id == account.tenant_id).all()
        assert len(rows) == 2
        by_date = {str(r.date): r for r in rows}
        assert by_date["2025-01-15"].amount == Decimal("-42.50")
        assert by_date["2025-01-16"].amount == Decimal("-142.50")
        assert by_date["2025-01-16"].statement_id == stmt2.id
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
