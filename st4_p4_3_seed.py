"""ST4 Phase 4.3 — seed DB with 5 users/tenants and statements for report stress test."""
import os
import random
from datetime import date, timedelta

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p43")
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"

os.environ["DATABASE_URL"] = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
os.environ["TAXFLOW_SINGLE_USER"] = "false"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager


def seed():
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
        db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

        for uidx in range(5):
            username = f"p43user{uidx}"
            user = db.query(models.User).filter(models.User.username == username).first()
            if user is None:
                crypto = LocalCryptoManager.create("password")
                user = models.User(
                    username=username,
                    email=f"{username}@example.com",
                    hashed_password=get_password_hash("password"),
                    encryption_salt=crypto.salt_b64,
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)

            client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
            if client is None:
                client = models.Client(name=f"P43 Tenant {uidx}", user_id=user.id)
                db.add(client)
                db.commit()
                db.refresh(client)

            account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
            if account is None:
                account = models.Account(
                    name="Checking", type="checking",
                    client_id=client.id, tenant_id=client.id, user_id=user.id,
                )
                db.add(account)
                db.commit()
                db.refresh(account)

            # 5 COA accounts
            for i in range(5):
                number = 1010 + i * 10
                coa = db.query(models.CoaAccount).filter(
                    models.CoaAccount.tenant_id == client.id,
                    models.CoaAccount.number == number,
                ).first()
                if coa is None:
                    coa = models.CoaAccount(
                        tenant_id=client.id, number=number,
                        name=f"Account {i+1}",
                        type="asset" if i % 2 == 0 else "expense",
                    )
                    db.add(coa)
                    db.commit()
                    db.refresh(coa)

            # Create 2 statements per user
            for sidx in range(2):
                statement = db.query(models.Statement).filter(
                    models.Statement.user_id == user.id,
                    models.Statement.filename == f"p43_stmt_{uidx}_{sidx}.csv"
                ).first()
                if statement is None:
                    statement = models.Statement(
                        user_id=user.id,
                        tenant_id=client.id,
                        account_id=account.id,
                        filename=f"p43_stmt_{uidx}_{sidx}.csv",
                        period_start=date(2026, 1, 1),
                        period_end=date(2026, 12, 31),
                        opening_balance=0.0,
                        closing_balance=0.0,
                        variance=0.0,
                        is_balanced=False,
                    )
                    db.add(statement)
                    db.commit()
                    db.refresh(statement)

                # Seed ~200 categorized transactions per statement
                tx_count = db.query(models.Transaction).filter(
                    models.Transaction.statement_id == statement.id
                ).count()
                if tx_count < 200:
                    batch = []
                    base = date(2026, 1, 1)
                    categories = ["office", "travel", "meals", "utilities", "software"]
                    for i in range(200 - tx_count):
                        amount = round(random.uniform(10.0, 1000.0), 2)
                        batch.append(models.Transaction(
                            statement_id=statement.id,
                            tenant_id=client.id,
                            user_id=user.id,
                            date=base + timedelta(days=i % 365),
                            description=f"Transaction {i+1}",
                            amount=amount,
                            tx_type="debit",
                            category=categories[i % len(categories)],
                        ))
                        if len(batch) >= 100:
                            db.bulk_save_objects(batch)
                            db.commit()
                            batch = []
                    if batch:
                        db.bulk_save_objects(batch)
                        db.commit()

            print(f"User {username}: tenant={client.id}, txns={db.query(models.Transaction).filter(models.Transaction.tenant_id == client.id).count()}")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    seed()
