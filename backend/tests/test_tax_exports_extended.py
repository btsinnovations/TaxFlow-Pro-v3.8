"""Tests for extended tax form exports (v3.11.6 R4)."""
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
from backend.accounting.tax_exports import form_1065, form_1120s, form_4562, form_8825, schedule_e


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
        client = models.Client(name="Extended Tax Client", user_id=auth_user.id)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        client = auth_user.clients[0]
    return auth_user, client


def _seed_statement_and_txn(db, account_id, tenant_id, user_id, **kwargs):
    statement = db.query(models.Statement).filter(models.Statement.account_id == account_id).first()
    if statement is None:
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename="tax.csv",
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


def test_form_1065_returns_expected_keys(db: Session):
    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4010", "Sales", "income")
    rent = create_account(db, client.id, user.id, "5100", "Rent", "expense")
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
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 5, 1),
        description="Sales",
        amount=Decimal("1000.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 5, 2),
        description="Rent",
        amount=Decimal("300.00"),
        tx_type="debit",
        coa_account_id=rent["id"],
    )
    result = form_1065(db, client.id, user.id, date(2026, 1, 1), date(2026, 12, 31))
    assert result["form"] == "1065"
    assert result["year"] == 2026
    assert "total_income" in result
    assert "total_expenses" in result
    assert "net_income" in result
    assert result["total_income"] == 1000.0
    assert result["total_expenses"] == 300.0


def test_form_1120s_returns_expected_keys(db: Session):
    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4020", "Service", "income")
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
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 6, 1),
        description="Service income",
        amount=Decimal("2500.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    result = form_1120s(db, client.id, user.id, date(2026, 1, 1), date(2026, 12, 31))
    assert result["form"] == "1120-S"
    assert result["total_income"] == 2500.0


def test_form_8825_and_schedule_e_map_lines(db: Session):
    user, client = _ensure_auth_user(db)
    rental_income = create_account(db, client.id, user.id, "4400", "Rental Income", "income")
    repairs = create_account(db, client.id, user.id, "5500", "Rental Repairs", "expense")
    from backend.accounting.tax_exports import set_mapping
    set_mapping(db, client.id, user.id, rental_income["id"], "8825", "2")
    set_mapping(db, client.id, user.id, repairs["id"], "Schedule E", "14")
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
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 7, 1),
        description="Rental income",
        amount=Decimal("800.00"),
        tx_type="credit",
        coa_account_id=rental_income["id"],
    )
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 7, 2),
        description="Rental repairs",
        amount=Decimal("150.00"),
        tx_type="debit",
        coa_account_id=repairs["id"],
    )
    result_8825 = form_8825(db, client.id, user.id, date(2026, 1, 1), date(2026, 12, 31))
    assert result_8825["form"] == "8825"
    assert result_8825["lines"]["income"].get("2") == 800.0
    result_e = schedule_e(db, client.id, user.id, date(2026, 1, 1), date(2026, 12, 31))
    assert result_e["form"] == "Schedule E"
    assert result_e["lines"]["expense"].get("14") == 150.0


def test_form_4562_pulls_depreciation(db: Session):
    user, client = _ensure_auth_user(db)
    asset = models.DepreciationAsset(
        tenant_id=client.id,
        user_id=user.id,
        name="Laptop",
        asset_class="5-year",
        cost_basis=Decimal("2000.00"),
        placed_in_service_date=date(2026, 1, 15),
        recovery_period_years=5,
        method="MACRS-GDS",
        convention="HY",
        section_179=Decimal("500.00"),
        bonus_depreciation=Decimal("0.00"),
        salvage_value=Decimal("0.00"),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    result = form_4562(db, client.id, user.id, 2026)
    assert result["form"] == "4562"
    assert result["year"] == 2026
    assert result["total_depreciation"] > 0
    assert result["lines"]["12"] == 500.0


def test_api_1065_endpoint(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4030", "API Sales", "income")
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
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 3, 1),
        description="API sales",
        amount=Decimal("900.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    resp = auth_client.post("/api/tax-exports/form-1065", json={
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["form"] == "1065"
    assert body["total_income"] == 900.0


def test_api_year_end_package_zip(auth_client: TestClient, db: Session):
    user, client = _ensure_auth_user(db)
    sales = create_account(db, client.id, user.id, "4040", "Pkg Sales", "income")
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
    _seed_statement_and_txn(
        db, account.id, client.id, user.id,
        date=date(2026, 4, 1),
        description="Pkg sales",
        amount=Decimal("500.00"),
        tx_type="credit",
        coa_account_id=sales["id"],
    )
    resp = auth_client.get("/api/tax-exports/year-end-package?year=2026")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    expected = {
        "trial_balance.csv",
        "income_statement.csv",
        "balance_sheet.json",
        "general_ledger.csv",
        "schedule_c.json",
        "schedule_c.csv",
        "form_1065.json",
        "form_1120s.json",
        "form_8825.json",
        "form_4562.json",
        "schedule_e.json",
        "form_1099_summary.csv",
        "review_flags.json",
        "workpaper_index.json",
    }
    assert expected.issubset(set(names)), f"missing files: {expected - set(names)}"
    index = json.loads(zf.read("workpaper_index.json"))
    assert index["year"] == 2026
    assert len(index["files"]) >= 10
