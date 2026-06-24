"""Tamper-evident hash-chain audit trail for TaxFlow Pro v3.9.

Each AuditEntry records an actor, action, resource type/id, and a timestamp.
In addition to the per-entry `entry_hash`, a `chain_hash` binds every row to
its predecessor: previous row's chain_hash + canonical JSON of the current row.
Removal or mutation of any prior row therefore breaks the chain. This is pure
local computation; no cloud dependency.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy.orm import Session

from backend.security.audit_sign import sign_entry, verify_entry_signature
from backend.utils.redaction import redact_pii, redact_pii_in_json

if TYPE_CHECKING:
    from backend.models import User, AuditEntry


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    EXPORT = "export"


class AuditResource(str, Enum):
    TRANSACTION = "transaction"
    STATEMENT = "statement"
    CLIENT = "client"
    ACCOUNT = "account"
    JOURNAL = "journal"
    PERIOD = "period"
    USER = "user"
    ASSET = "asset"
    CATEGORIZATION_RULE = "categorization_rule"
    FLAG = "flag"
    GENERAL_LEDGER_ENTRY = "general_ledger_entry"
    EXPORT = "export"


_GENESIS_HASH = "0" * 64


def _normalize_dt(value: Optional[datetime]) -> str:
    """Return deterministic ISO string for hashing.

    All timestamps are stored in UTC; any tzinfo is stripped so the serialized
    value is stable across Python/DB combinations.
    """
    if value is None:
        return ""
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _redact_details(details: Optional[dict]) -> dict:
    """Return a PII-redacted, JSON-safe dict for inclusion in the hash."""
    if details is None:
        return {}
    return redact_pii_in_json(dict(details))


def _canonical_json(
    entry_id: int,
    occurred_at: datetime,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    user_id: int,
    tenant_id: Optional[int],
    details: dict,
) -> str:
    """Stable canonical representation of the auditable fields of one row."""
    payload = {
        "id": entry_id,
        "occurred_at": _normalize_dt(occurred_at),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "details": details,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _compute_chain_hash(
    previous_chain_hash: str,
    entry_id: int,
    occurred_at: datetime,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    user_id: int,
    tenant_id: Optional[int],
    details: dict,
) -> str:
    """SHA-256 of previous chain hash + canonical JSON of current entry."""
    canonical = _canonical_json(
        entry_id=entry_id,
        occurred_at=occurred_at,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        tenant_id=tenant_id,
        details=details,
    )
    return hashlib.sha256((previous_chain_hash + canonical).encode("utf-8")).hexdigest()


def _hash_entry(
    previous_hash: str,
    occurred_at: datetime,
    actor_id: int,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    details: dict,
) -> str:
    """Legacy per-entry hash (retained for backwards compatibility)."""
    payload = {
        "previous_hash": previous_hash,
        "occurred_at": _normalize_dt(occurred_at),
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _chain_hash_for_entry(entry: "AuditEntry", previous_chain_hash: str) -> str:
    """Compute the expected chain_hash for an existing AuditEntry row."""
    from backend.models import AuditEntry  # noqa: F401 - local import for typing

    details: dict = {}
    if entry.details:
        try:
            details = json.loads(entry.details)
        except (json.JSONDecodeError, TypeError):
            details = {"_raw": str(entry.details)}
    details = _redact_details(details)

    return _compute_chain_hash(
        previous_chain_hash=previous_chain_hash,
        entry_id=entry.id,
        occurred_at=entry.occurred_at,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        user_id=entry.actor_id,
        tenant_id=None,
        details=details,
    )


def _verify_signature_for_entry(entry: "AuditEntry") -> bool:
    """Return True if the entry's Ed25519 signature is valid."""
    if not entry.signature:
        return False
    details: dict = {}
    if entry.details:
        try:
            details = json.loads(entry.details)
        except (json.JSONDecodeError, TypeError):
            details = {"_raw": str(entry.details)}
    details = _redact_details(details)
    return verify_entry_signature(
        signature_b64=entry.signature,
        entry_id=entry.id,
        occurred_at=_normalize_dt(entry.occurred_at),
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        user_id=entry.actor_id,
        tenant_id=None,
        details=details,
        chain_hash=entry.chain_hash or _GENESIS_HASH,
    )


from backend.audit.append_only import _set_audit_entries_mutable


def record(
    db: Session,
    actor: "User",
    action: AuditAction,
    resource_type: AuditResource,
    resource_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> "AuditEntry":
    """Create a new AuditEntry, redact PII, and append it to the chain."""
    from backend.models import AuditEntry  # local import to avoid circular refs

    occurred_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Use the most recent entry's chain_hash as the link for this row.
    previous = db.query(AuditEntry).order_by(AuditEntry.id.desc()).first()
    previous_chain_hash = previous.chain_hash if previous and previous.chain_hash else _GENESIS_HASH

    # Copy details so callers are not mutated, then redact PII from free-text
    # and JSON details before hashing/persistence.
    details_copy = dict(details) if details else {}
    description = redact_pii(details_copy.pop("description", ""))
    safe_details = _redact_details(details_copy)

    entry_hash = _hash_entry(
        previous_hash=previous_chain_hash,
        occurred_at=occurred_at,
        actor_id=actor.id,
        action=action.value,
        resource_type=resource_type.value,
        resource_id=resource_id,
        details=safe_details,
    )

    entry = AuditEntry(
        occurred_at=occurred_at,
        actor_id=actor.id,
        action=action.value,
        resource_type=resource_type.value,
        resource_id=resource_id,
        description=description,
        details=json.dumps(safe_details),
        previous_hash=previous_chain_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    db.flush()

    entry.chain_hash = _compute_chain_hash(
        previous_chain_hash=previous_chain_hash,
        entry_id=entry.id,
        occurred_at=entry.occurred_at,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        user_id=entry.actor_id,
        tenant_id=None,
        details=safe_details,
    )

    entry.signature = sign_entry(
        entry_id=entry.id,
        occurred_at=_normalize_dt(entry.occurred_at),
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        user_id=entry.actor_id,
        tenant_id=None,
        details=safe_details,
        chain_hash=entry.chain_hash,
    )

    # The audit trail is append-only. Mutating the freshly-inserted row to set
    # the chain_hash is the one legitimate UPDATE; use the management escape
    # hatch for this single statement.
    with _set_audit_entries_mutable():
        db.commit()
    db.refresh(entry)
    return entry


def verify_chain(db: Session) -> Tuple[bool, Optional[str]]:
    """Walk every audit entry in id order and verify chain_hash + signature.

    Returns (True, None) when the chain is intact, otherwise (False, id) where
    id is the first row whose stored chain_hash or signature does not verify.
    """
    from backend.models import AuditEntry

    entries = db.query(AuditEntry).order_by(AuditEntry.id.asc()).all()
    previous_hash = _GENESIS_HASH
    for entry in entries:
        expected = _chain_hash_for_entry(entry, previous_hash)
        if expected != entry.chain_hash:
            return False, str(entry.id)
        if not _verify_signature_for_entry(entry):
            return False, str(entry.id)
        previous_hash = entry.chain_hash
    return True, None


def backfill_chain_hashes(db: Session) -> int:
    """Compute and persist chain_hash for every AuditEntry that lacks one.

    Existing hashes are recomputed in id order so the chain remains
    deterministic. Returns the number of rows updated.
    """
    from backend.models import AuditEntry

    entries = db.query(AuditEntry).order_by(AuditEntry.id.asc()).all()
    previous_hash = _GENESIS_HASH
    updated = 0
    for entry in entries:
        expected = _chain_hash_for_entry(entry, previous_hash)
        if entry.chain_hash != expected:
            entry.chain_hash = expected
            updated += 1
        previous_hash = expected
    if updated:
        db.commit()
    return updated
