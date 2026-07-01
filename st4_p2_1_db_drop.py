"""Stress Test 4 Phase 2.1 - Simulated mid-transaction DB drop using pg_terminate_backend."""
import os
import sys
import time

TEST_DB = os.environ.get("ST4_TEST_DB")
if not TEST_DB:
    print("Set ST4_TEST_DB env var")
    sys.exit(1)

ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"
os.environ["DATABASE_URL"] = ADMIN_URL

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import date
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager


def seed(db):
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    user = db.query(models.User).filter(models.User.username == "dbdrop").first()
    if user is None:
        crypto = LocalCryptoManager.create("password")
        user = models.User(
            username="dbdrop",
            email="dbdrop@example.com",
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
        client = models.Client(name="DB Drop Client", user_id=user.id)
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

    return user, client, account, coa


def get_backend_pid(session):
    return session.execute(text("SELECT pg_backend_pid()")).scalar()


def main():
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    user, client, account, coa = seed(db)
    user_id = user.id
    tenant_id = client.id
    db.close()
    engine.dispose()

    e0 = create_engine(ADMIN_URL)
    db0 = sessionmaker(bind=e0)()
    db0.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db0.execute(text(f"SELECT set_config('taxflow.tenant_id', '{tenant_id}', false)"))
    baseline = db0.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id).count()
    db0.close()
    e0.dispose()

    print(f"Baseline transactions: {baseline}")
    print("Opening long-lived transaction, inserting row, then killing backend PID mid-flight...")

    tx_engine = create_engine(ADMIN_URL)
    tx_session = sessionmaker(bind=tx_engine)()
    try:
        tx_session.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
        tx_session.execute(text(f"SELECT set_config('taxflow.tenant_id', '{tenant_id}', false)"))

        tx = models.Transaction(
            statement_id=1,
            tenant_id=tenant_id,
            user_id=user_id,
            date=date(2026, 7, 1),
            description="mid-flight drop test",
            amount=9999.0,
            tx_type="debit",
            category="uncategorized",
        )
        tx_session.add(tx)
        tx_session.flush()
        in_flight_pid = get_backend_pid(tx_session)
        print(f"  in-flight backend PID: {in_flight_pid}")

        admin_engine = create_engine(ADMIN_URL)
        admin = sessionmaker(bind=admin_engine)()
        admin.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": in_flight_pid})
        admin.commit()
        admin.close()
        admin_engine.dispose()

        print("  backend terminated; attempting commit...")
        tx_session.commit()
        print("  commit unexpectedly succeeded")
        committed = True
    except Exception as ex:
        print(f"  commit failed as expected: {ex}")
        try:
            tx_session.rollback()
        except Exception:
            pass
        committed = False
    finally:
        try:
            tx_session.close()
        except Exception:
            pass
        try:
            tx_engine.dispose()
        except Exception:
            pass

    time.sleep(2)
    e1 = create_engine(ADMIN_URL)
    db1 = sessionmaker(bind=e1)()
    db1.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db1.execute(text(f"SELECT set_config('taxflow.tenant_id', '{tenant_id}', false)"))
    final = db1.query(models.Transaction).filter(models.Transaction.tenant_id == tenant_id).count()
    db1.close()
    e1.dispose()

    print(f"\nPhase 2.1 Mid-Transaction DB Drop Results:")
    print(f"  baseline tx count: {baseline}")
    print(f"  final tx count: {final}")
    print(f"  committed flag: {committed}")
    print(f"  no leaked row: {final == baseline}")

    if (not committed) and final == baseline:
        print("\nPHASE 2.1 RESULT: PASS (in-flight transaction rolled back cleanly)")
    else:
        print("\nPHASE 2.1 RESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
