"""Local encryption primitives for data-at-rest protection.

Design goals:
- No external network dependencies.
- User master password derives a key via Argon2id.
- Optional keyfile provides an additional key factor.
- Data is encrypted with AES-256-GCM using a randomly generated data key
  that is itself encrypted by the master-derived key.
- All operations are deterministic given the same inputs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


class EncryptionError(Exception):
    pass


class AuthenticationError(Exception):
    pass


# Argon2id parameters tuned for interactive master-password derivation.
# These can be raised later for stronger resistance; memory=64MB keeps
# local logins fast while still being costly to brute-force.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 65536  # 64 MB
ARGON2_PARALLELISM = 1

# Version marker for serialized envelope format.
ENVELOPE_VERSION = 1


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password and salt using Argon2id."""
    kdf = Argon2id(
        salt=salt,
        length=32,
        iterations=ARGON2_TIME_COST,
        lanes=ARGON2_PARALLELISM,
        memory_cost=ARGON2_MEMORY_COST_KIB,
    )
    return kdf.derive(password.encode("utf-8"))


def _build_keyfile_key(keyfile_path: Optional[Path]) -> bytes:
    """Return a 32-byte key derived from an optional keyfile.

    If no keyfile is provided, returns a zero-key so downstream logic stays
    uniform. The keyfile content is hashed with SHA-3_256 for stability.
    """
    if keyfile_path is None:
        return b"\x00" * 32
    if not keyfile_path.exists():
        raise EncryptionError(f"Keyfile not found: {keyfile_path}")
    data = keyfile_path.read_bytes()
    if len(data) < 32:
        raise EncryptionError("Keyfile must be at least 32 bytes")
    return hashlib.sha3_256(data).digest()


def _combine_keys(password_key: bytes, keyfile_key: bytes) -> bytes:
    """Combine two 32-byte keys into a single 32-byte key via SHA-3_256."""
    return hashlib.sha3_256(password_key + keyfile_key).digest()


@dataclass(frozen=True)
class KeyBundle:
    """Container for derived encryption key and its inputs (except password)."""

    salt: bytes
    keyfile_path: Optional[Path]


class LocalCryptoManager:
    """Encrypt/decrypt data with a user-derived key.

    Typical flow:
        1. manager = LocalCryptoManager.create(password, keyfile_path)
        2. ciphertext = manager.encrypt(plaintext)
        3. plaintext = manager.decrypt(ciphertext)
    """

    def __init__(self, key: bytes, salt: bytes, keyfile_path: Optional[Path] = None):
        if len(key) != 32:
            raise EncryptionError("Encryption key must be 32 bytes")
        self._key = key
        self._salt = salt
        self._keyfile_path = keyfile_path

    @classmethod
    def create(
        cls,
        password: str,
        keyfile_path: Optional[Path] = None,
        salt: Optional[bytes] = None,
    ) -> "LocalCryptoManager":
        """Create a new manager, generating a random salt if not provided."""
        salt = salt or secrets.token_bytes(16)
        if len(salt) < 16:
            raise EncryptionError("Salt must be at least 16 bytes")
        password_key = _derive_key(password, salt)
        keyfile_key = _build_keyfile_key(keyfile_path)
        combined = _combine_keys(password_key, keyfile_key)
        return cls(combined, salt, keyfile_path)

    @classmethod
    def from_stored(
        cls,
        password: str,
        salt_b64: str | None,
        keyfile_path: Optional[Path] = None,
    ) -> "LocalCryptoManager":
        """Recreate a manager from stored salt and user password."""
        if not salt_b64:
            raise EncryptionError("Stored salt is required to derive encryption key")
        salt = base64.b64decode(salt_b64)
        return cls.create(password, keyfile_path, salt=salt)

    @property
    def salt_b64(self) -> str:
        return base64.b64encode(self._salt).decode("ascii")

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Encrypt plaintext using AES-256-GCM. Returns versioned envelope."""
        if not isinstance(plaintext, bytes):
            raise TypeError("plaintext must be bytes")
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        envelope = {
            "v": ENVELOPE_VERSION,
            "salt_b64": self.salt_b64,
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        }
        return json.dumps(envelope).encode("utf-8")

    def decrypt(self, envelope_bytes: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Decrypt an envelope produced by encrypt()."""
        try:
            envelope = json.loads(envelope_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise EncryptionError("Invalid envelope") from exc
        if envelope.get("v") != ENVELOPE_VERSION:
            raise EncryptionError("Unsupported envelope version")
        nonce = base64.b64decode(envelope["nonce_b64"])
        ciphertext = base64.b64decode(envelope["ciphertext_b64"])
        aesgcm = AESGCM(self._key)
        try:
            return aesgcm.decrypt(nonce, ciphertext, associated_data)
        except Exception as exc:
            raise AuthenticationError("Decryption failed: wrong password or corrupted data") from exc


def generate_keyfile(path: Path, size: int = 64) -> Path:
    """Generate a cryptographically random keyfile and write it to disk."""
    if size < 32:
        raise ValueError("Keyfile size must be at least 32 bytes")
    path = Path(path)
    path.write_bytes(secrets.token_bytes(size))
    return path


def generate_local_secret_key() -> str:
    """Generate a URL-safe secret key for local JWT signing."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Runtime cache of per-user column-encryption managers.
# The manager is derived from the user's master password + stored salt and is
# kept only in memory. It is set at boot/login and cleared at logout.
# ---------------------------------------------------------------------------
_column_crypto_lock = threading.Lock()
_column_crypto_managers: dict[int, LocalCryptoManager] = {}


def register_column_crypto_manager(
    user_id: int,
    password: str,
    salt_b64: str,
    keyfile_path: Optional[Path] = None,
) -> LocalCryptoManager:
    """Derive and cache a column-encryption manager for a user."""
    manager = LocalCryptoManager.from_stored(password, salt_b64, keyfile_path)
    with _column_crypto_lock:
        _column_crypto_managers[user_id] = manager
    return manager


def get_column_crypto_manager(user_id: int) -> Optional[LocalCryptoManager]:
    """Return the cached column-encryption manager for a user, if any."""
    with _column_crypto_lock:
        return _column_crypto_managers.get(user_id)


def clear_column_crypto_manager(user_id: int) -> None:
    """Remove the cached column-encryption manager (e.g., on logout)."""
    with _column_crypto_lock:
        _column_crypto_managers.pop(user_id, None)
