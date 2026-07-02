"""ST4 Phase 7 — seed DB with one user and an account for parser edge-case tests."""
import os
from datetime import date

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p7")
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

        user = db.query(models.User).filter(models.User.username == "p7user").first()
        if user is None:
            crypto = LocalCryptoManager.create("password")
            user = models.User(
                username="p7user",
                email="p7@example.com",
                hashed_password=get_password_hash("password"),
                encryption_salt=crypto.salt_b64,
                is_active=True,
            )
            db.add(user); db.commit(); db.refresh(user)

        client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
        if client is None:
            client = models.Client(name="P7 Tenant", user_id=user.id)
            db.add(client); db.commit(); db.refresh(client)

        account = db.query(models.Account).filter(models.Account.user_id == user.id).first()
        if account is None:
            account = models.Account(
                name="Checking", type="checking",
                client_id=client.id, tenant_id=client.id, user_id=user.id,
            )
            db.add(account); db.commit(); db.refresh(account)

        print("Phase 7 seed complete.")
        print(f"  user: p7user / password")
        print(f"  tenant_id: {client.id}")
        print(f"  account_id: {account.id}")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    seed()
