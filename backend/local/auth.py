"""Local-only authentication for TaxFlow Pro.

This module replaces cloud-oriented OAuth/email verification with a master
password + optional keyfile model. All credentials are verified locally; no
network access is required.
"""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from typing import Optional

from .crypto import LocalCryptoManager, AuthenticationError, EncryptionError


class LocalAuthError(Exception):
    pass


class InvalidPasswordError(LocalAuthError):
    pass


class UserAlreadyExistsError(LocalAuthError):
    pass


class UserNotFoundError(LocalAuthError):
    pass


def _constant_time_compare(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class LocalAuthManager:
    """Manage local user identity, password hashing, and session tokens.

    Passwords are hashed with SHA-3_256 + random salt. This avoids pulling in
    bcrypt dependency conflicts and keeps hashing deterministic and fast on all
    platforms. SHA-3_256 is used for storage only; the key derivation for data
    encryption still uses Argon2id in crypto.py.
    """

    SALT_LENGTH = 32

    def __init__(self, db_session, crypto_manager: Optional[LocalCryptoManager] = None):
        self._db = db_session
        self._crypto = crypto_manager

    @staticmethod
    def _hash_password(password: str, salt: bytes) -> bytes:
        """Return SHA-3_256 hash of password + salt."""
        return hashlib.sha3_256(password.encode("utf-8") + salt).digest()

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = secrets.token_bytes(cls.SALT_LENGTH)
        hashed = cls._hash_password(password, salt)
        return f"{salt.hex()}:{hashed.hex()}"

    @classmethod
    def verify_password(cls, password: str, stored: str) -> bool:
        try:
            salt_hex, hash_hex = stored.split(":", 1)
        except ValueError:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = cls._hash_password(password, salt)
        return secrets.compare_digest(expected, bytes.fromhex(hash_hex))

    def register(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        keyfile_path: Optional[Path] = None,
    ):
        """Register a new local user.

        If a keyfile path is provided, the user's data encryption key is derived
        from both the password and the keyfile.
        """
        from .. import models

        existing = self._db.query(models.User).filter(models.User.username == username).first()
        if existing:
            raise UserAlreadyExistsError(f"User {username} already exists")

        # Use provided keyfile or None; store salt in the user record.
        crypto = LocalCryptoManager.create(password, keyfile_path)
        hashed = self.hash_password(password)

        user = models.User(
            username=username,
            email=email or "",
            hashed_password=hashed,
            encryption_salt=crypto.salt_b64,
            keyfile_path=str(keyfile_path) if keyfile_path else None,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def authenticate(self, username: str, password: str, keyfile_path: Optional[Path] = None):
        """Verify credentials and return the user record if valid."""
        from .. import models

        user = self._db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise InvalidPasswordError("Invalid username or password")
        if not self.verify_password(password, user.hashed_password):
            raise InvalidPasswordError("Invalid username or password")

        # Validate keyfile matches stored path if one was configured.
        if user.keyfile_path:
            if keyfile_path is None:
                raise LocalAuthError("Keyfile required for this account")
            if Path(user.keyfile_path).resolve() != Path(keyfile_path).resolve():
                raise LocalAuthError("Keyfile mismatch")

        return user

    def get_crypto_manager(self, user, password: str) -> LocalCryptoManager:
        """Return a crypto manager for the user after verifying password."""
        keyfile_path = Path(user.keyfile_path) if user.keyfile_path else None
        return LocalCryptoManager.create(password, keyfile_path, salt=user.encryption_salt)


def create_session_token() -> str:
    """Generate a secure opaque session token."""
    return secrets.token_urlsafe(32)
