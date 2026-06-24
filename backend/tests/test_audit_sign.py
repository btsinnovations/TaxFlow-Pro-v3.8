"""Tests for TASK-030: asymmetric Ed25519 audit entry signatures."""

import pytest

from backend.security.audit_sign import (
    public_key_pem,
    reset_private_key,
    sign_entry,
    verify_entry_signature,
)


PASS = "T4xFl0w-2026!Secure"


def test_public_key_is_valid_pem():
    pem = public_key_pem()
    assert "BEGIN PUBLIC KEY" in pem
    assert "END PUBLIC KEY" in pem


def test_sign_and_verify_entry():
    chain_hash = "abcd" * 16
    sig = sign_entry(
        entry_id=1,
        occurred_at="2026-06-21T12:00:00.000000",
        action="create",
        resource_type="client",
        resource_id=42,
        user_id=7,
        tenant_id=3,
        details={"note": "test"},
        chain_hash=chain_hash,
    )
    assert sig
    assert verify_entry_signature(
        signature_b64=sig,
        entry_id=1,
        occurred_at="2026-06-21T12:00:00.000000",
        action="create",
        resource_type="client",
        resource_id=42,
        user_id=7,
        tenant_id=3,
        details={"note": "test"},
        chain_hash=chain_hash,
    )


def test_signature_fails_when_payload_tampered():
    chain_hash = "abcd" * 16
    sig = sign_entry(
        entry_id=1,
        occurred_at="2026-06-21T12:00:00.000000",
        action="create",
        resource_type="client",
        resource_id=42,
        user_id=7,
        tenant_id=3,
        details={"note": "test"},
        chain_hash=chain_hash,
    )
    assert not verify_entry_signature(
        signature_b64=sig,
        entry_id=2,  # tampered
        occurred_at="2026-06-21T12:00:00.000000",
        action="create",
        resource_type="client",
        resource_id=42,
        user_id=7,
        tenant_id=3,
        details={"note": "test"},
        chain_hash=chain_hash,
    )


def test_verify_with_only_public_key():
    pem = public_key_pem()
    chain_hash = "efgh" * 16
    sig = sign_entry(
        entry_id=5,
        occurred_at="2026-06-21T12:00:00.000000",
        action="update",
        resource_type="account",
        resource_id=10,
        user_id=2,
        tenant_id=None,
        details={},
        chain_hash=chain_hash,
    )
    assert verify_entry_signature(
        signature_b64=sig,
        entry_id=5,
        occurred_at="2026-06-21T12:00:00.000000",
        action="update",
        resource_type="account",
        resource_id=10,
        user_id=2,
        tenant_id=None,
        details={},
        chain_hash=chain_hash,
        public_key_pem_str=pem,
    )


def test_audit_record_gets_signature(client):
    """Recording an audit entry writes a signature that verifies."""
    from backend.tests.test_hybrid_auth import _reset_db
    from backend.tests.conftest import TestingSessionLocal
    from backend.audit import record, AuditAction, AuditResource
    from backend.models import User

    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": PASS})
    assert resp.status_code == 200

    db = TestingSessionLocal()
    user = db.query(User).filter(User.username != "").first()
    assert user is not None

    entry = record(
        db,
        user,
        AuditAction.CREATE,
        AuditResource.CLIENT,
        resource_id=1,
        details={"name": "Acme"},
    )
    assert entry.signature is not None
    assert entry.signature != ""

    # Verify the stored signature.
    from backend.audit.audit_trail import _verify_signature_for_entry

    assert _verify_signature_for_entry(entry)


def test_verify_chain_detects_missing_signature(client):
    """If an entry's signature is cleared, verify_chain reports it invalid."""
    from backend.tests.test_hybrid_auth import _reset_db
    from backend.tests.conftest import TestingSessionLocal
    from backend.audit import record, AuditAction, AuditResource, verify_chain
    from backend.audit.append_only import _set_audit_entries_mutable
    from backend.models import User, AuditEntry

    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": PASS})
    assert resp.status_code == 200

    db = TestingSessionLocal()
    user = db.query(User).filter(User.username != "").first()
    record(db, user, AuditAction.CREATE, AuditResource.CLIENT, resource_id=1)

    # Tamper: remove the signature using the append-only escape hatch.
    entry = db.query(AuditEntry).order_by(AuditEntry.id.desc()).first()
    with _set_audit_entries_mutable():
        entry.signature = None
        db.commit()

    valid, first_bad_id = verify_chain(db)
    assert valid is False
    assert first_bad_id == str(entry.id)


def test_verify_endpoint_reports_signature_status(client):
    """The /api/audit/verify endpoint includes signature-aware validity."""
    from backend.tests.test_hybrid_auth import _reset_db

    _reset_db()
    boot = client.post("/api/auth/boot", json={"password": PASS})
    assert boot.status_code == 200
    token = boot.json()["access_token"]

    resp = client.get("/api/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["first_bad_id"] is None
