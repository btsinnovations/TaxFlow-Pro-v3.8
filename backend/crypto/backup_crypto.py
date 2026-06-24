"""Authenticated encryption helpers for TaxFlow Pro backups.

Backups are encrypted with a key derived from the local JWT signing secret,
so a backup can only be restored on the same machine/profile that created it.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import struct
import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

# Header format:
#   magic (4 bytes): b"TFBU"
#   version (1 byte): unsigned uint8
#   salt_length (2 bytes): unsigned uint16, big-endian
#   salt (salt_length bytes)
#   ciphertext (remaining bytes)
MAGIC = b"TFBU"
FORMAT_VERSION = 1
SALT_LEN = 32


class BackupCryptoError(Exception):
    pass


def _derive_backup_key(local_secret: str, salt: bytes, iterations: int = 480_000) -> bytes:
    """Derive a Fernet-compatible key via PBKDF2-HMAC-SHA256.

    Returns a URL-safe base64-encoded 32-byte key suitable for Fernet.
    """
    raw_key = hashlib.pbkdf2_hmac(
        "sha256",
        local_secret.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )
    return base64.urlsafe_b64encode(raw_key)


def derive_backup_key(local_secret: str, salt: bytes) -> bytes:
    """Public alias matching the TASK-020 signature."""
    return _derive_backup_key(local_secret, salt)


def _generate_salt() -> bytes:
    return secrets.token_bytes(SALT_LEN)


def _encode_header(salt: bytes, version: int = FORMAT_VERSION) -> bytes:
    return MAGIC + struct.pack("!B", version) + struct.pack("!H", len(salt)) + salt


def _decode_header(data: bytes) -> tuple[int, bytes, bytes]:
    """Parse header and return (version, salt, ciphertext)."""
    if len(data) < len(MAGIC) + 3:
        raise BackupCryptoError("Backup file too small to contain a valid header")
    if not data.startswith(MAGIC):
        raise BackupCryptoError("Backup file is not a TaxFlow encrypted backup")
    version = struct.unpack("!B", data[len(MAGIC) : len(MAGIC) + 1])[0]
    salt_len = struct.unpack("!H", data[len(MAGIC) + 1 : len(MAGIC) + 3])[0]
    header_end = len(MAGIC) + 3 + salt_len
    if len(data) < header_end:
        raise BackupCryptoError("Backup header truncated")
    salt = data[len(MAGIC) + 3 : header_end]
    ciphertext = data[header_end:]
    return version, salt, ciphertext


def encrypt_backup(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt plaintext backup bytes using Fernet.

    ``key`` is the Fernet-compatible key produced by ``derive_backup_key``.
    """
    salt = _generate_salt()
    fernet = Fernet(key)
    ciphertext = fernet.encrypt(plaintext)
    return _encode_header(salt) + ciphertext


def decrypt_backup(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt a TaxFlow encrypted backup.

    ``key`` is the Fernet-compatible key produced by ``derive_backup_key``.
    The salt embedded in the header is ignored by Fernet (Fernet tokens carry
    their own salt), but the header is validated for format correctness.
    """
    try:
        _version, _salt, encrypted_payload = _decode_header(ciphertext)
    except BackupCryptoError:
        raise
    if not encrypted_payload:
        raise BackupCryptoError("Backup file contains no encrypted payload")
    fernet = Fernet(key)
    try:
        return fernet.decrypt(encrypted_payload)
    except InvalidToken as exc:
        raise BackupCryptoError("Backup decryption failed; local secret may have changed") from exc


def encrypt_backup_with_secret(plaintext: bytes, local_secret: str) -> bytes:
    """Convenience wrapper: derive a fresh key from ``local_secret`` and encrypt."""
    salt = _generate_salt()
    key = _derive_backup_key(local_secret, salt)
    fernet = Fernet(key)
    ciphertext = fernet.encrypt(plaintext)
    return _encode_header(salt) + ciphertext


def decrypt_backup_with_secret(ciphertext: bytes, local_secret: str) -> bytes:
    """Convenience wrapper: extract salt from header, derive key, and decrypt."""
    version, salt, encrypted_payload = _decode_header(ciphertext)
    if version != FORMAT_VERSION:
        raise BackupCryptoError(f"Unsupported backup format version: {version}")
    key = _derive_backup_key(local_secret, salt)
    fernet = Fernet(key)
    try:
        return fernet.decrypt(encrypted_payload)
    except InvalidToken as exc:
        raise BackupCryptoError("Backup decryption failed; local secret may have changed") from exc
