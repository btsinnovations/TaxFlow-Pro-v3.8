"""
Audit trail system with cryptographic hash chaining for TaxFlow Pro.

Every audit entry is linked to the previous entry via SHA-256 hash,
forming an immutable chain per client.  This provides tamper-evident
logging for all financial mutations.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action constants
# ---------------------------------------------------------------------------

ACTION_CREATE_TRANSACTION = "CREATE_TRANSACTION"
ACTION_UPDATE_TRANSACTION = "UPDATE_TRANSACTION"
ACTION_DELETE_TRANSACTION = "DELETE_TRANSACTION"
ACTION_LOCK_PERIOD = "LOCK_PERIOD"
ACTION_UNLOCK_PERIOD = "UNLOCK_PERIOD"
ACTION_POST_JOURNAL = "POST_JOURNAL"
ACTION_UPLOAD_RECEIPT = "UPLOAD_RECEIPT"
ACTION_SIGN_REPORT = "SIGN_REPORT"
ACTION_ARCHIVE_YEAR = "ARCHIVE_YEAR"
ACTION_RESTORE_YEAR = "RESTORE_YEAR"
ACTION_CREATE_STATEMENT = "CREATE_STATEMENT"
ACTION_UPDATE_CLIENT = "UPDATE_CLIENT"
ACTION_DELETE_CLIENT = "DELETE_CLIENT"
ACTION_CREATE_JOURNAL = "CREATE_JOURNAL"
ACTION_UPDATE_JOURNAL = "UPDATE_JOURNAL"
ACTION_DELETE_JOURNAL = "DELETE_JOURNAL"

ALL_ACTIONS = {
    ACTION_CREATE_TRANSACTION,
    ACTION_UPDATE_TRANSACTION,
    ACTION_DELETE_TRANSACTION,
    ACTION_LOCK_PERIOD,
    ACTION_UNLOCK_PERIOD,
    ACTION_POST_JOURNAL,
    ACTION_UPLOAD_RECEIPT,
    ACTION_SIGN_REPORT,
    ACTION_ARCHIVE_YEAR,
    ACTION_RESTORE_YEAR,
    ACTION_CREATE_STATEMENT,
    ACTION_UPDATE_CLIENT,
    ACTION_DELETE_CLIENT,
    ACTION_CREATE_JOURNAL,
    ACTION_UPDATE_JOURNAL,
    ACTION_DELETE_JOURNAL,
}


# ---------------------------------------------------------------------------
# Hash chain helpers
# ---------------------------------------------------------------------------

def _serialize_value(value: Any) -> str:
    """JSON-serialize a value, handling dates and decimals."""
    if value is None:
        return "null"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _compute_event_hash(
    previous_hash: str,
    action: str,
    entity_type: str,
    entity_id: int,
    old_values: Optional[Dict[str, Any]],
    new_values: Optional[Dict[str, Any]],
    timestamp: str,
    user_id: int,
    client_id: Optional[int],
) -> str:
    """
    Compute SHA-256 hash of the current event chained to *previous_hash*.

    The serialized payload includes all event fields to ensure any
    tampering is detectable.
    """
    payload = {
        "previous_hash": previous_hash,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_values": old_values,
        "new_values": new_values,
        "timestamp": timestamp,
        "user_id": user_id,
        "client_id": client_id,
    }
    serialized = json.dumps(payload, sort_keys=True, default=_serialize_value)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _get_genesis_hash(client_id: Optional[int]) -> str:
    """Return the genesis hash for a client (or system-wide)."""
    if client_id is not None:
        return hashlib.sha256(f"{client_id}:genesis".encode("utf-8")).hexdigest()
    return hashlib.sha256("system:genesis".encode("utf-8")).hexdigest()


def _get_previous_hash(db: Session, client_id: Optional[int]) -> str:
    """
    Query the most recent audit entry for *client_id* and return its
    hash.  If no prior entry exists, return the genesis hash.
    """
    query = db.query(models.AuditEntry)
    if client_id is not None:
        query = query.filter(models.AuditEntry.tenant_id == client_id)
    else:
        query = query.filter(models.AuditEntry.tenant_id.is_(None))

    last_entry = query.order_by(models.AuditEntry.id.desc()).first()

    if last_entry is None:
        return _get_genesis_hash(client_id)

    # Reconstruct the last entry's hash from stored details if available
    if last_entry.details:
        try:
            details = json.loads(last_entry.details)
            stored_hash = details.get("hash")
            if stored_hash:
                return stored_hash
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: hash the last entry's core data as the chain link
    fallback_payload = {
        "action": last_entry.action,
        "entity_type": last_entry.entity_type,
        "entity_id": last_entry.entity_id,
        "user_id": last_entry.user_id,
        "timestamp": last_entry.created_at.isoformat() if last_entry.created_at else "",
    }
    return hashlib.sha256(
        json.dumps(fallback_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_audit_entry(
    db: Session,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    client_id: Optional[int] = None,
) -> models.AuditEntry:
    """
    Create a tamper-evident audit entry with hash chaining.

    Args:
        db: SQLAlchemy session.
        user_id: ID of the user performing the action.
        action: One of the ACTION_* constants.
        entity_type: Model name of the affected entity.
        entity_id: Primary key of the affected entity.
        old_values: Optional dict of previous field values.
        new_values: Optional dict of new field values.
        client_id: Tenant/client ID for scope (None for system-wide events).

    Returns:
        The created AuditEntry instance (already flushed but **not** committed).

    Raises:
        ValueError: If *action* is not a recognized action constant.
    """
    if action not in ALL_ACTIONS:
        raise ValueError(f"Unrecognized audit action: {action}")

    now = datetime.now(timezone.utc)

    # Resolve previous hash in the chain
    previous_hash = _get_previous_hash(db, client_id)

    # Create the entry first so we can use the persisted created_at timestamp
    # for hashing. This guarantees create and verify use the exact same value.
    entry = models.AuditEntry(
        tenant_id=client_id if client_id is not None else 0,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_at=now,
        details="",
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)

    timestamp = entry.created_at.isoformat() if entry.created_at else now.isoformat()

    # Compute current entry hash
    current_hash = _compute_event_hash(
        previous_hash=previous_hash,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        timestamp=timestamp,
        user_id=user_id,
        client_id=client_id,
    )

    # Build human-readable details + embedded hash
    details_dict: Dict[str, Any] = {
        "hash": current_hash,
        "previous_hash": previous_hash,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "timestamp": timestamp,
    }
    if old_values is not None:
        details_dict["old_values"] = old_values
    if new_values is not None:
        details_dict["new_values"] = new_values

    entry.details = json.dumps(details_dict, default=_serialize_value)
    db.flush()

    logger.debug(
        "Audit entry created: action=%s entity=%s:%s hash=%s...",
        action,
        entity_type,
        entity_id,
        current_hash[:12],
    )

    return entry


def verify_chain_integrity(db: Session, client_id: Optional[int] = None) -> list:
    """
    Verify the hash chain for a client's audit entries.

    Returns a list of dicts with ``entry_id``, ``expected_hash``,
    ``stored_hash``, and ``valid`` boolean.  An empty list means no
    entries to verify.
    """
    query = db.query(models.AuditEntry)
    if client_id is not None:
        query = query.filter(models.AuditEntry.tenant_id == client_id)
    else:
        query = query.filter(models.AuditEntry.tenant_id.is_(None))

    entries = query.order_by(models.AuditEntry.id.asc()).all()
    if not entries:
        return []

    results = []
    previous_hash = _get_genesis_hash(client_id)

    for entry in entries:
        try:
            details = json.loads(entry.details) if entry.details else {}
            stored_hash = details.get("hash", "")
        except (json.JSONDecodeError, TypeError):
            stored_hash = ""

        expected_hash = _compute_event_hash(
            previous_hash=previous_hash,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            old_values=details.get("old_values"),
            new_values=details.get("new_values"),
            timestamp=entry.created_at.isoformat() if entry.created_at else "",
            user_id=entry.user_id,
            client_id=client_id,
        )

        results.append({
            "entry_id": entry.id,
            "expected_hash": expected_hash,
            "stored_hash": stored_hash,
            "valid": stored_hash == expected_hash,
        })
        previous_hash = expected_hash

    return results
