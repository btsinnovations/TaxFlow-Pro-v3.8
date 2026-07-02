"""ST4 Phase 6.1 — seed DB with 500K transactions for pagination stress."""
import os
import random
from datetime import date, timedelta

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p61")
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

        user = db.query(models.User).filter(models.User.username == "p61user").first()
        if user is None:
            crypto = LocalCryptoManager.create("password")
            user = models.User(
                username="p61user",
                email="p61@example.com",
                hashed_password=get_password_hash("password"),
                encryption_salt=crypto.salt_b64,
                is_active=True,
            )
            db.add(user); db.commit(); db.refresh(user)

        client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
        if client is None:
            client = models.Client(name="P61 Tenant", user_id=user.id)
            db.add(client); db.commit(); db.refresh(client)

        account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
        if account is None:
            account = models.Account(
                name="Checking", type="checking",
                client_id=client.id, tenant_id=client.id, user_id=user.id,
            )
            db.add(account); db.commit(); db.refresh(account)

        # Create a Statement (required FK for transactions)
        statement = db.query(models.Statement).filter(
            models.Statement.user_id == user.id
        ).first()
        if statement is None:
            statement = models.Statement(
                user_id=user.id,
                tenant_id=client.id,
                account_id=account.id,
                filename="p61_seed.csv",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
                opening_balance=0.0,
                closing_balance=0.0,
                variance=0.0,
                is_balanced=False,
            )
            db.add(statement); db.commit(); db.refresh(statement)

        target = 500_000
        existing = db.query(models.Transaction).filter(
            models.Transaction.tenant_id == client.id
        ).count()
        if existing < target:
            print(f"Seeding {target - existing} transactions...")
            base = date(2026, 1, 1)
            batch = []
            for i in range(target - existing):
                batch.append(models.Transaction(
                    statement_id=statement.id,
                    tenant_id=client.id,
                    user_id=user.id,
                    date=base + timedelta(days=i % 365),
                    description=f"Txn {existing + i + 1}",
                    amount=round(random.uniform(1.0, 1000.0), 2),
                    tx_type="debit",
                    category="uncategorized",
                ))
                if len(batch) >= 5000:
                    db.bulk_save_objects(batch)
                    db.commit()
                    batch = []
            if batch:
                db.bulk_save_objects(batch)
                db.commit()

        print("Phase 6.1 seed complete.")
        print(f"  user: p61user / password")
        print(f"  tenant_id: {client.id}")
        print(f"  transactions: {db.query(models.Transaction).filter(models.Transaction.tenant_id == client.id).count()}")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    seed()
