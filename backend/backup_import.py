"""v3.10 -> v3.11 backup import logic.

Accepts a JSON backup object produced by TaxFlow Pro v3.10 and imports users,
clients, GL accounts, accounts, statements, and transactions into the current
v3.11 database. IDs are remapped to avoid collisions with existing data.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from . import models


class BackupImportError(Exception):
    """Raised when the backup payload cannot be imported safely."""


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value.replace("Z", "+00:00").split("T")[0])
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Be tolerant of trailing Z and date-only strings.
        cleaned = value.replace("Z", "+00:00")
        if "T" not in cleaned:
            cleaned += "T00:00:00+00:00"
        return datetime.fromisoformat(cleaned)
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def import_v3_10_backup(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Import a v3.10 JSON backup and return remapped ID summary."""
    schema_version = payload.get("version", "3.10.0")
    if not schema_version.startswith("3.10"):
        raise BackupImportError(f"Unsupported backup version: {schema_version}")

    id_maps = {
        "users": {},
        "clients": {},
        "gl_accounts": {},
        "accounts": {},
        "statements": {},
    }
    counts: Dict[str, int] = {
        "users": 0,
        "clients": 0,
        "gl_accounts": 0,
        "accounts": 0,
        "statements": 0,
        "transactions": 0,
    }

    users_in = payload.get("users", [])
    for old in users_in:
        # Skip users that already exist by username or email.
        existing = (
            db.query(models.User)
            .filter(
                (models.User.username == old.get("username"))
                | (models.User.email == old.get("email"))
            )
            .first()
        )
        if existing:
            id_maps["users"][old["id"]] = existing.id
            continue
        user = models.User(
            username=old.get("username"),
            email=old.get("email"),
            hashed_password=old.get("hashed_password"),
            encryption_salt=old.get("encryption_salt"),
            keyfile_path=old.get("keyfile_path"),
            is_active=old.get("is_active", True),
            created_at=_parse_datetime(old.get("created_at")) or datetime.utcnow(),
        )
        db.add(user)
        db.flush()
        id_maps["users"][old["id"]] = user.id
        counts["users"] += 1

    clients_in = payload.get("clients", [])
    for old in clients_in:
        owner_id = id_maps["users"].get(old.get("user_id"))
        if not owner_id:
            continue
        existing = (
            db.query(models.Client)
            .filter(models.Client.name == old.get("name"), models.Client.user_id == owner_id)
            .first()
        )
        if existing:
            id_maps["clients"][old["id"]] = existing.id
            continue
        client = models.Client(
            name=old.get("name"),
            email=old.get("email"),
            tax_id=old.get("tax_id"),
            user_id=owner_id,
            created_at=_parse_datetime(old.get("created_at")) or datetime.utcnow(),
        )
        db.add(client)
        db.flush()
        id_maps["clients"][old["id"]] = client.id
        counts["clients"] += 1

    gl_accounts_in = payload.get("gl_accounts", [])
    for old in gl_accounts_in:
        tenant_id = id_maps["clients"].get(old.get("tenant_id"))
        user_id = id_maps["users"].get(old.get("user_id"))
        if not tenant_id or not user_id:
            continue
        existing = (
            db.query(models.GLAccount)
            .filter(
                models.GLAccount.code == old.get("code"),
                models.GLAccount.tenant_id == tenant_id,
            )
            .first()
        )
        if existing:
            id_maps["gl_accounts"][old["id"]] = existing.id
            continue
        gl_account = models.GLAccount(
            tenant_id=tenant_id,
            user_id=user_id,
            code=old.get("code"),
            name=old.get("name"),
            account_type=old.get("account_type", "expense"),
            is_active=old.get("is_active", True),
            created_at=_parse_datetime(old.get("created_at")) or datetime.utcnow(),
        )
        db.add(gl_account)
        db.flush()
        id_maps["gl_accounts"][old["id"]] = gl_account.id
        counts["gl_accounts"] += 1

    accounts_in = payload.get("accounts", [])
    for old in accounts_in:
        tenant_id = id_maps["clients"].get(old.get("tenant_id"))
        client_id = id_maps["clients"].get(old.get("client_id"), tenant_id)
        user_id = id_maps["users"].get(old.get("user_id"))
        if not tenant_id or not user_id:
            continue
        existing = (
            db.query(models.Account)
            .filter(
                models.Account.account_number_masked == old.get("account_number_masked"),
                models.Account.tenant_id == tenant_id,
            )
            .first()
        )
        if existing:
            id_maps["accounts"][old["id"]] = existing.id
            continue
        account = models.Account(
            name=old.get("name"),
            institution=old.get("institution"),
            account_number_masked=old.get("account_number_masked"),
            type=old.get("type", "checking"),
            client_id=client_id,
            tenant_id=tenant_id,
            user_id=user_id,
            created_at=_parse_datetime(old.get("created_at")) or datetime.utcnow(),
        )
        db.add(account)
        db.flush()
        id_maps["accounts"][old["id"]] = account.id
        counts["accounts"] += 1

    statements_in = payload.get("statements", [])
    for old in statements_in:
        account_id = id_maps["accounts"].get(old.get("account_id"))
        tenant_id = id_maps["clients"].get(old.get("tenant_id"))
        user_id = id_maps["users"].get(old.get("user_id"))
        if not account_id or not tenant_id or not user_id:
            continue
        statement = models.Statement(
            account_id=account_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename=old.get("filename"),
            period_start=_parse_date(old.get("period_start")),
            period_end=_parse_date(old.get("period_end")),
            opening_balance=_to_decimal(old.get("opening_balance")),
            closing_balance=_to_decimal(old.get("closing_balance")),
            variance=_to_decimal(old.get("variance")),
            is_balanced=old.get("is_balanced"),
            created_at=_parse_datetime(old.get("created_at")) or datetime.utcnow(),
        )
        db.add(statement)
        db.flush()
        id_maps["statements"][old["id"]] = statement.id
        counts["statements"] += 1

    transactions_in = payload.get("transactions", [])
    for old in transactions_in:
        statement_id = id_maps["statements"].get(old.get("statement_id"))
        tenant_id = id_maps["clients"].get(old.get("tenant_id"))
        user_id = id_maps["users"].get(old.get("user_id"))
        gl_account_id = id_maps["gl_accounts"].get(old.get("gl_account_id"))
        if not statement_id or not tenant_id or not user_id:
            continue
        txn = models.Transaction(
            statement_id=statement_id,
            tenant_id=tenant_id,
            user_id=user_id,
            gl_account_id=gl_account_id,
            date=_parse_date(old.get("date")),
            description=old.get("description"),
            amount=_to_decimal(old.get("amount")),
            tx_type=old.get("tx_type"),
            category=old.get("category", "uncategorized"),
            running_balance=_to_decimal(old.get("running_balance")),
            workpaper_ref=old.get("workpaper_ref"),
            txn_uid=old.get("txn_uid"),
            fitid=old.get("fitid"),
            import_source=old.get("import_source"),
            created_at=_parse_datetime(old.get("created_at")) or datetime.utcnow(),
        )
        db.add(txn)
        counts["transactions"] += 1

    db.commit()
    return {
        "schema_version": schema_version,
        "id_maps": id_maps,
        "counts": counts,
    }
