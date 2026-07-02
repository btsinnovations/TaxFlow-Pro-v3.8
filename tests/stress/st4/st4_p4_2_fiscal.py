"""Stress Test 4 Phase 4.2 — Fiscal Year Boundary Smashing."""
import os
import sys

TEST_DB = os.environ.get("ST4_TEST_DB")
if not TEST_DB:
    print("Set ST4_TEST_DB env var")
    sys.exit(1)

TEST_URL = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"

os.environ["DATABASE_URL"] = TEST_URL
os.environ["TAXFLOW_SINGLE_USER"] = "false"

from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.api import app
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager
from backend.accounting.period_close import is_period_closed, close_period


def seed(db):
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    user = db.query(models.User).filter(models.User.username == "fiscal").first()
    if user is None:
        crypto = LocalCryptoManager.create("password")
        user = models.User(
            username="fiscal",
            email="fiscal@example.com",
            hashed_password=get_password_hash("password"),
            encryption_salt=crypto.salt_b64,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.encryption_salt:
        crypto = LocalCryptoManager.create("password")
        user.encryption_salt = crypto.salt_b64
        db.add(user)
        db.commit()
        db.refresh(user)

    client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
    if client is None:
        client = models.Client(name="Fiscal Client", user_id=user.id)
        db.add(client)
        db.commit()
        db.refresh(client)

    account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
    if account is None:
        account = models.Account(name="Checking", type="checking", client_id=client.id, tenant_id=client.id, user_id=user.id)
        db.add(account)
        db.commit()
        db.refresh(account)

    coa = db.query(models.CoaAccount).filter(models.CoaAccount.tenant_id == client.id, models.CoaAccount.number == 1010).first()
    if coa is None:
        coa = models.CoaAccount(tenant_id=client.id, number=1010, name="Cash", type="asset")
        db.add(coa)
        db.commit()
        db.refresh(coa)

    period = db.query(models.Period).filter(
        models.Period.tenant_id == client.id,
        models.Period.start_date == date(2026, 12, 1),
    ).first()
    if period is None:
        period = models.Period(
            tenant_id=client.id,
            user_id=user.id,
            name="Dec 2026",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 31),
            is_closed=False,
        )
        db.add(period)
        db.commit()
        db.refresh(period)

    return user, client, account, coa, period


def login_client(tenant_id):
    c = TestClient(app)
    c.headers["X-Tenant-ID"] = str(tenant_id)
    r = c.post("/api/auth/login", data={"username": "fiscal", "password": "password"})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return c


def post_txn(client, account_id, coa_id, txn_date, amount):
    payload = {
        "account_id": account_id,
        "date": txn_date.isoformat(),
        "description": f"FY boundary {txn_date}",
        "amount": amount,
        "tx_type": "debit",
        "category": "uncategorized",
        "coa_account_id": coa_id,
    }
    return client.post("/api/transactions", json=payload)


def main():
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    user, client, account, coa, period = seed(db)
    tenant_id = client.id
    user_id = user.id
    account_id = account.id
    coa_id = coa.id
    period_id = period.id
    db.close()
    engine.dispose()

    c = login_client(tenant_id)

    # Test dates spanning FY boundary.
    cases = [
        ("2026-12-31", date(2026, 12, 31)),
        ("2027-01-01", date(2027, 1, 1)),
        ("2026-12-31 last instant", date(2026, 12, 31)),
        ("2027-01-01 first instant", date(2027, 1, 1)),
    ]

    results = []
    amount = 1.0
    for label, txn_date in cases:
        r = post_txn(c, account_id, coa_id, txn_date, amount)
        ok = r.status_code == 201
        stored = None
        if ok:
            admin_engine = create_engine(ADMIN_URL)
            adb = sessionmaker(bind=admin_engine)()
            adb.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
            tx = adb.query(models.Transaction).filter(
                models.Transaction.tenant_id == tenant_id,
                models.Transaction.date == txn_date.isoformat(),
            ).first()
            stored = tx.date if tx else None
            adb.close()
            admin_engine.dispose()
        results.append((label, txn_date, r.status_code, ok, stored))
        amount += 1.0

    # Now close 2026 and verify 2026 posting is blocked, 2027 posting still allowed.
    admin_engine = create_engine(ADMIN_URL)
    db2 = sessionmaker(bind=admin_engine)()
    db2.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db2.execute(text(f"SELECT set_config('taxflow.tenant_id', '{tenant_id}', false)"))
    close_period(db2, tenant_id=tenant_id, user_id=user_id, period_id=period_id)
    db2.commit()
    closed_2026 = is_period_closed(db2, tenant_id, date(2026, 12, 31))
    closed_2027 = is_period_closed(db2, tenant_id, date(2027, 1, 1))
    db2.close()
    admin_engine.dispose()

    r_2026 = post_txn(c, account_id, coa_id, date(2026, 12, 31), 99.0)
    r_2027 = post_txn(c, account_id, coa_id, date(2027, 1, 1), 99.0)

    print("\nPhase 4.2 Fiscal Year Boundary Results:")
    for label, txn_date, status, ok, stored in results:
        verdict = "PASS" if (ok and stored == txn_date) else "FAIL"
        print(f"  {label:30} status={status} stored={stored} {verdict}")
    print(f"  2026-12 period closed: {closed_2026}")
    print(f"  2027-01 period closed: {closed_2027}")
    print(f"  post-close 2026 tx status: {r_2026.status_code}")
    print(f"  post-close 2027 tx status: {r_2027.status_code}")

    all_ok = all(ok and stored == d for _, d, _, ok, stored in results)
    all_ok = all_ok and closed_2026 and not closed_2027 and r_2026.status_code != 201 and r_2027.status_code == 201
    if all_ok:
        print("\nPHASE 4.2 RESULT: PASS")
    else:
        print("\nPHASE 4.2 RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
