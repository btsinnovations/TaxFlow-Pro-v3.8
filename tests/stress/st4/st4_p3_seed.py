"""ST4 Phase 3 — seed a fresh PostgreSQL DB with 10k GL entries + CJK/German txns."""
import os
import sys
import random
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TEST_DB = os.environ.get("ST4_TEST_DB", "taxflow_stress_4_p3")
ADMIN_URL = f"postgresql://postgres@localhost:5433/{TEST_DB}"

os.environ["DATABASE_URL"] = f"postgresql://taxflow_test:taxflow_test@localhost:5433/{TEST_DB}"
os.environ["TAXFLOW_SINGLE_USER"] = "false"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend import models
from backend.routers.auth import get_password_hash
from backend.local.crypto import LocalCryptoManager


def seed(db):
    db.execute(text("SELECT set_config('taxflow.service_role', 'on', false)"))
    db.execute(text("SELECT set_config('taxflow.tenant_id', '', false)"))

    user = db.query(models.User).filter(models.User.username == "phase3").first()
    if user is None:
        crypto = LocalCryptoManager.create("password")
        user = models.User(
            username="phase3",
            email="phase3@example.com",
            hashed_password=get_password_hash("password"),
            encryption_salt=crypto.salt_b64,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.encryption_salt:
        user.encryption_salt = LocalCryptoManager.create("password").salt_b64
        db.add(user)
        db.commit()
        db.refresh(user)

    client = db.query(models.Client).filter(models.Client.user_id == user.id).first()
    if client is None:
        client = models.Client(name="Phase 3 Tenant", user_id=user.id)
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

    # Create a Statement (required FK for transactions)
    statement = db.query(models.Statement).filter(
        models.Statement.user_id == user.id
    ).first()
    if statement is None:
        statement = models.Statement(
            user_id=user.id,
            tenant_id=client.id,
            account_id=account.id,
            filename="p3_seed.csv",
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

    # Create 10 GL accounts
    gl_accounts = []
    for i in range(10):
        number = 1010 + i * 10
        ga = db.query(models.CoaAccount).filter(
            models.CoaAccount.tenant_id == client.id,
            models.CoaAccount.number == number,
        ).first()
        if ga is None:
            ga = models.CoaAccount(
                tenant_id=client.id,
                number=number,
                name=f"Test Account {i+1}",
                type="asset" if i % 2 == 0 else "expense",
            )
            db.add(ga)
            db.commit()
            db.refresh(ga)
        gl_accounts.append(ga)

    # Bulk-create 10,000 general ledger entries
    existing = db.query(models.GeneralLedgerEntry).filter(
        models.GeneralLedgerEntry.tenant_id == client.id
    ).count()
    target = 10_000
    if existing < target:
        print(f"Seeding {target - existing} GL entries...")
        base = date(2026, 1, 1)
        batch = []
        for i in range(target - existing):
            acct = gl_accounts[i % len(gl_accounts)]
            d = base + timedelta(days=i % 365)
            amount = round(random.uniform(1.0, 1000.0), 2)
            batch.append(models.GeneralLedgerEntry(
                tenant_id=client.id,
                user_id=user.id,
                date=d,
                description=f"GL entry {existing + i + 1}",
                debit_coa_account_id=acct.id,
                credit_coa_account_id=acct.id,
                amount=amount,
                memo="",
                entry_type="regular",
            ))
            if len(batch) >= 500:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
        if batch:
            db.bulk_save_objects(batch)
            db.commit()

    # Create 200 transactions with CJK / German descriptions
    existing_tx = db.query(models.Transaction).filter(
        models.Transaction.tenant_id == client.id
    ).count()
    target_tx = 200
    if existing_tx < target_tx:
        print(f"Seeding {target_tx - existing_tx} transactions...")
        descriptions = [
            "Kauf von Büromaterial und Druckerpatronen für den gesamten Betrieb",
            "会議室のリース料金およびケータリングサービス支払い",
            "Neuwagenbeschaffung für Vertriebsmitarbeiter in Norddeutschland",
            "ソフトウェアライセンス更新費用とクラウドストレージ利用料",
            "Reparatur und Wartung der Klimaanlage im Hauptgebäude",
            "給与振込手数料及び年末調整関連の事務経費",
            "Marketingkampagne für neue Produktlinie im vierten Quartal",
            "税金申告用のコンサルティング料金支払い完了",
        ]
        batch = []
        base = date(2026, 1, 1)
        for i in range(target_tx - existing_tx):
            batch.append(models.Transaction(
                statement_id=statement.id,
                tenant_id=client.id,
                user_id=user.id,
                date=base + timedelta(days=i % 365),
                description=descriptions[i % len(descriptions)],
                amount=round(random.uniform(10.0, 5000.0), 2),
                tx_type="debit",
                category="uncategorized",
            ))
            if len(batch) >= 100:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
        if batch:
            db.bulk_save_objects(batch)
            db.commit()

    print("Phase 3 seed complete.")
    print(f"  tenant_id: {client.id}")
    print(f"  user: phase3 / password")
    print(f"  GL entries: {db.query(models.GeneralLedgerEntry).filter(models.GeneralLedgerEntry.tenant_id == client.id).count()}")
    print(f"  transactions: {db.query(models.Transaction).filter(models.Transaction.tenant_id == client.id).count()}")


if __name__ == "__main__":
    engine = create_engine(ADMIN_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        seed(db)
    finally:
        db.close()
        engine.dispose()
