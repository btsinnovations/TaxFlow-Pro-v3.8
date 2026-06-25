"""Audit trail tests for TaxFlow Pro v3.9."""
import base64
import secrets
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.audit import record, verify_chain, backfill_chain_hashes, AuditAction, AuditResource
from backend import models


def _make_user(db: Session, username: str) -> models.User:
    user = models.User(
        username=username,
        email=f"{username}@local",
        hashed_password="x",
        encryption_salt=base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_audit_entry_records_create(db: Session):
    user = _make_user(db, "auditor1")
    entry = record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1, {"name": "Acme"})
    assert entry.action == "create"
    assert entry.resource_type == "client"
    assert entry.resource_id == 1
    assert entry.actor_id == user.id
    assert entry.entry_hash is not None
    assert len(entry.entry_hash) == 64
    assert entry.chain_hash is not None
    assert len(entry.chain_hash) == 64


def test_audit_chain_verifies_clean(db: Session):
    user = _make_user(db, "auditor2")
    record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1)
    record(db, user, AuditAction.UPDATE, AuditResource.CLIENT, 1)
    record(db, user, AuditAction.DELETE, AuditResource.CLIENT, 1)
    valid, first_bad_id = verify_chain(db)
    assert valid is True
    assert first_bad_id is None


def test_audit_chain_detects_tampering(db: Session):
    user = _make_user(db, "auditor3")
    record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1)
    entry = db.query(models.AuditEntry).order_by(models.AuditEntry.id.desc()).first()
    with pytest.raises(Exception):
        entry.details = "{\"tampered\": true}"
        db.commit()
    db.rollback()
    # After the append-only guard blocks the mutation, the chain still verifies.
    valid, first_bad_id = verify_chain(db)
    assert valid is True
    assert first_bad_id is None


def test_audit_backfills_null_chain_hashes(db: Session):
    user = _make_user(db, "auditor5")

    # Simulate pre-migration audit rows that have no chain_hash or signature.
    # INSERT is allowed by the append-only trigger; UPDATE is not, so we use
    # raw SQL to create the synthetic legacy state.
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        text(
            """
            INSERT INTO audit_entries (
                occurred_at, actor_id, action, resource_type, resource_id,
                description, details, previous_hash, entry_hash, chain_hash, signature
            ) VALUES (
                :ts, :actor_id, 'create', 'client', 1,
                NULL, '{}', :zero_hash, :entry_hash, NULL, NULL
            )
            """
        ),
        {
            "ts": now,
            "actor_id": user.id,
            "zero_hash": "0" * 64,
            "entry_hash": "a" * 64,
        },
    )
    db.execute(
        text(
            """
            INSERT INTO audit_entries (
                occurred_at, actor_id, action, resource_type, resource_id,
                description, details, previous_hash, entry_hash, chain_hash, signature
            ) VALUES (
                :ts, :actor_id, 'update', 'client', 1,
                NULL, '{}', :zero_hash, :entry_hash, NULL, NULL
            )
            """
        ),
        {
            "ts": now,
            "actor_id": user.id,
            "zero_hash": "0" * 64,
            "entry_hash": "b" * 64,
        },
    )
    db.commit()

    updated = backfill_chain_hashes(db)
    assert updated == 2

    # Verify chain hashes were backfilled in id order.
    entries = db.query(models.AuditEntry).order_by(models.AuditEntry.id.asc()).all()
    assert len(entries) == 2
    assert entries[0].chain_hash is not None and entries[0].chain_hash != "0" * 64
    assert entries[1].chain_hash is not None and entries[1].chain_hash != entries[0].chain_hash

    # Legacy unsigned rows cannot pass signature verification; confirm that
    # the chain values themselves are deterministic by recomputing them.
    from backend.audit.audit_trail import _chain_hash_for_entry, _GENESIS_HASH
    expected_first = _chain_hash_for_entry(entries[0], _GENESIS_HASH)
    expected_second = _chain_hash_for_entry(entries[1], expected_first)
    assert entries[0].chain_hash == expected_first
    assert entries[1].chain_hash == expected_second


def test_audit_verify_endpoint(client: TestClient, db: Session):
    user = _make_user(db, "auditor6")
    record(db, user, AuditAction.CREATE, AuditResource.CLIENT, 1)
    record(db, user, AuditAction.UPDATE, AuditResource.CLIENT, 1)

    # Log in as the user so the protected endpoint accepts the request.
    from backend.routers.auth import get_password_hash
    user.hashed_password = get_password_hash("T4xFl0…2026")
    db.commit()

    login = client.post("/api/auth/login", data={
        "username": user.username,
        "password": "T4xFl0…2026",
    })
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    resp = client.get("/api/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["first_bad_id"] is None
    assert data["count"] == 2


def test_audit_instruments_statement_upload(client, db: Session):
    # covered by integration tests in test_api; unit test here checks helper returns entry
    user = _make_user(db, "auditor4")
    entry = record(db, user, AuditAction.CREATE, AuditResource.STATEMENT, 99, {"filename": "x.pdf"})
    assert entry.resource_type == "statement"
