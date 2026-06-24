"""Application-level column encryption helpers for TaxFlow Pro v3.9.1.

These helpers encrypt/decrypt individual sensitive columns using the per-user
AES-256-GCM manager cached in backend.local.crypto. They are intentionally
explicit so that routers control exactly which fields are encrypted at rest
and which are returned as plaintext over the API.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from backend.local.crypto import (
    EncryptionError,
    AuthenticationError,
    get_column_crypto_manager,
)

if TYPE_CHECKING:
    from backend.models import User


def _looks_encrypted(value: str) -> bool:
    """Heuristic: encrypted values are JSON envelopes produced by AESGCM."""
    if not value:
        return False
    return value.strip().startswith('{"v":')


def encrypt_for_user(plaintext: Optional[str], user: "User") -> Optional[str]:
    """Encrypt plaintext for a user, or return it unchanged if no manager exists."""
    if plaintext is None:
        return None
    manager = get_column_crypto_manager(user.id)
    if manager is None:
        # No manager cached yet (should not happen after login/boot). Store as-is
        # rather than raising, so the app remains usable if encryption is disabled.
        return plaintext
    return manager.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_for_user(ciphertext: Optional[str], user: "User") -> Optional[str]:
    """Decrypt ciphertext for a user. Falls back to raw value if not encrypted."""
    if ciphertext is None:
        return None
    if not _looks_encrypted(ciphertext):
        return ciphertext
    manager = get_column_crypto_manager(user.id)
    if manager is None:
        # No manager available; cannot decrypt. Return ciphertext so caller can
        # at least see that data exists rather than losing it silently.
        return ciphertext
    try:
        return manager.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (EncryptionError, AuthenticationError, KeyError, ValueError):
        return ciphertext
