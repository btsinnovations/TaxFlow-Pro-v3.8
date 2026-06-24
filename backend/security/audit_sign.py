"""Asymmetric Ed25519 signing for audit entries (TASK-030).

- Private key is loaded from `TAXFLOW_AUDIT_PRIVATE_KEY_PATH` or generated
  deterministically from the app's local secret (fallback for dev/test only).
- Public key is exposed via `audit_public_key_pem()`.
- Each audit entry is signed over its chain_hash + canonical entry fields.
- Verification replays the canonical payload and checks the signature.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _get_local_secret() -> bytes:
    """Return the raw local secret bytes (lazy import to avoid cycles)."""
    from backend import auth

    return auth.get_local_secret()


def _load_or_create_private_key(path: str | None = None) -> Ed25519PrivateKey:
    """Load the Ed25519 audit signing private key.

    Priority:
      1. `path` argument
      2. `TAXFLOW_AUDIT_PRIVATE_KEY_PATH` env var
      3. Deterministic key derived from the local secret (dev/test fallback)
    """
    key_path = path or os.environ.get("TAXFLOW_AUDIT_PRIVATE_KEY_PATH")
    if key_path and Path(key_path).exists():
        pem = Path(key_path).read_bytes()
        return serialization.load_pem_private_key(pem, password=None)

    # Fallback: deterministic derivation from local secret. Not recommended for
    # production because rotating the app secret would also rotate the audit key.
    secret = _get_local_secret()
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    seed = hashlib.sha256(b"taxflow-audit-key-v1:" + secret).digest()[:32]
    return Ed25519PrivateKey.from_private_bytes(seed)


def _private_key() -> Ed25519PrivateKey:
    """Module-level lazy singleton for the audit private key."""
    if not hasattr(_private_key, "_key"):
        _private_key._key = _load_or_create_private_key()  # type: ignore[attr-defined]
    return _private_key._key  # type: ignore[attr-defined,return-value]


def reset_private_key(path: str | None = None) -> None:
    """Reset the cached private key (used mainly by tests)."""
    _private_key._key = _load_or_create_private_key(path)  # type: ignore[attr-defined]


def public_key_pem() -> str:
    """Return the public key as a PEM-encoded string."""
    public = _private_key().public_key()
    return public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _signing_payload(
    entry_id: int,
    occurred_at: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    user_id: int,
    tenant_id: Optional[int],
    details: dict,
    chain_hash: str,
) -> bytes:
    """Canonical bytes signed for each audit entry."""
    import json

    payload = {
        "id": entry_id,
        "occurred_at": occurred_at,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "details": details,
        "chain_hash": chain_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign_entry(
    entry_id: int,
    occurred_at: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    user_id: int,
    tenant_id: Optional[int],
    details: dict,
    chain_hash: str,
) -> str:
    """Return a base64-ish URL-safe signature string for an audit entry."""
    payload = _signing_payload(
        entry_id=entry_id,
        occurred_at=occurred_at,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        tenant_id=tenant_id,
        details=details,
        chain_hash=chain_hash,
    )
    sig = _private_key().sign(payload)
    import base64

    return base64.urlsafe_b64encode(sig).decode("ascii")


def verify_entry_signature(
    signature_b64: str,
    entry_id: int,
    occurred_at: str,
    action: str,
    resource_type: str,
    resource_id: Optional[int],
    user_id: int,
    tenant_id: Optional[int],
    details: dict,
    chain_hash: str,
    public_key_pem_str: Optional[str] = None,
) -> bool:
    """Verify an audit entry signature.

    If `public_key_pem_str` is provided, it is used instead of the cached private
    key's public key. This allows offline verification with only the public key.
    """
    import base64

    if public_key_pem_str:
        public_key = serialization.load_pem_public_key(public_key_pem_str.encode("utf-8"))
    else:
        public_key = _private_key().public_key()

    payload = _signing_payload(
        entry_id=entry_id,
        occurred_at=occurred_at,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        tenant_id=tenant_id,
        details=details,
        chain_hash=chain_hash,
    )
    try:
        sig = base64.urlsafe_b64decode(signature_b64.encode("ascii"))
        public_key.verify(sig, payload)
        return True
    except Exception:
        return False
