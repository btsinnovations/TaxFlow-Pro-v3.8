"""Tests for year-end package zip download (v3.11.6 R4)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend import models
from backend.accounting.coa import create_account


def _ensure_auth_user(db: Session):
    auth_user = db.query(models.User).filter(models.User.username == "testuser").first()
    if auth_user is None:
        from backend.routers.auth import get_password_hash
        auth_user = models.User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("T4xFl0…2026"),
            is_active=True,
        )
        db.add(auth_user)
        db.commit()
        db.refresh(auth_user)
    if not auth_user.clients:
        client = models.Client(name="YearEnd Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def _seed_txn(db, account_id, tenant_id, user_id, **kwargs):
    statement = db.query(models.Statement).filter(models.Statement.account_id == account_id).first()
    if statement is None:
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="ye.csv",
        )
        db.add(statement)
        db.commit()
        db.refresh(statement)
    txn = models.Transaction(
        statement_id=statement.id,
        tenant_id=tenant_id,
        user_id=user_id,
        **kwargs,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def test_year_end_package_contains_all_files(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4050", "Year Sales", "income")
    supplies = create_account(db, client.id, user.id, "5200", "Supplies", "expense")
    account = models.Account(
        name="Checking",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    _seed_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 5, 1),
        description="Sales",
        amount=Decimal("1000.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    _seed_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 5, 2),
        description="Supplies",
        amount=Decimal("200.00"),
        tx_type="debit",
        coa_account_id=supplies["id"],
    )
    resp = auth_client.get("/api/tax-exports/year-end-package?year=2026")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    required = {
        "trial_balance.csv",
        "income_statement.csv",
        "balance_sheet.json",
        "general_ledger.csv",
        "schedule_c.json",
        "form_1065.json",
        "form_1120s.json",
        "form_8825.json",
        "form_4562.json",
        "schedule_e.json",
        "form_1099_summary.csv",
        "review_flags.json",
        "workpaper_index.json",
    }
    assert required.issubset(set(names)), f"missing: {required - set(names)}"
    index = json.loads(zf.read("workpaper_index.json").decode("utf-8"))
    assert index["year"] == 2026
    assert len(index["files"]) >= 10


def test_year_end_package_income_statement_matches(db: Session):
    from backend.accounting.year_end import generate_year_end_package

    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4060", "Pkg Sales", "income")
    account = models.Account(
        name="Checking",
        type="checking",
        client_id=client.id,
        tenant_id=client.id,
        user_id=user.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    _seed_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 4, 1),
        description="Pkg income",
        amount=Decimal("600.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    zip_bytes = generate_year_end_package(db, client.id, user.id, 2026)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    schedule_c_json = json.loads(zf.read("schedule_c.json").decode("utf-8"))
    assert schedule_c_json["line_1_gross_receipts"] == 600.0
