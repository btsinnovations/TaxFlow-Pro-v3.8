"""Local-only authentication for TaxFlow Pro.

This module replaces cloud-oriented OAuth/email verification with a master
password + optional keyfile model. All credentials are verified locally; no
network access is required.

Password hashing migration (v3.9.1):
- New hashes use bcrypt (canonical, matching backend/auth.py).
- Legacy SHA-3_256 hashes (format ``salt_hex:hash_hex``) are still accepted
  for login. On successful verification the stored hash is transparently
  rehashed with bcrypt.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path
from typing import Optional

import bcrypt

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

    Password hashing uses bcrypt for new hashes. Legacy SHA-3_256 hashes
    (format ``salt_hex:hash_hex``) remain verifiable for one successful login,
    after which they are transparently migrated to bcrypt.
    """

    SALT_LENGTH = 32
    _LEGACY_HASH_RE = re.compile(r"^[0-9a-f]{64}:[0-9a-f]{64}$")

    def __init__(self, db_session, crypto_manager: Optional[LocalCryptoManager] = None):
        self._db = db_session
        self._crypto = crypto_manager

    @staticmethod
    def _legacy_hash_password(password: str, salt: bytes) -> bytes:
        """Return SHA-3_256 hash of password + salt (legacy algorithm)."""
        return hashlib.sha3_256(password.encode("utf-8") + salt).digest()

    @classmethod
    def _is_legacy_hash(cls, stored: str) -> bool:
        return bool(cls._LEGACY_HASH_RE.match(stored))

    @classmethod
    def _verify_legacy_password(cls, password: str, stored: str) -> bool:
        try:
            salt_hex, hash_hex = stored.split(":", 1)
        except ValueError:
            return False
        try:
            salt = bytes.fromhex(salt_hex)
            expected = cls._legacy_hash_password(password, salt)
            return secrets.compare_digest(expected, bytes.fromhex(hash_hex))
        except (ValueError, OSError):
            return False

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Return a bcrypt hash for new passwords."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @classmethod
    def verify_password(cls, password: str, stored: str) -> bool:
        """Verify a password against either a bcrypt or a legacy SHA-3_256 hash."""
        if cls._is_legacy_hash(stored):
            return cls._verify_legacy_password(password, stored)
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except (ValueError, OSError):
            return False

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
        """Verify credentials and return the user record if valid.

        Legacy SHA-3_256 hashes are accepted for one successful login and
        are transparently rehashed with bcrypt before the user is returned.
        """
        from .. import models

        user = self._db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise InvalidPasswordError("Invalid username or password")
        if not self.verify_password(password, user.hashed_password):
            raise InvalidPasswordError("Invalid username or password")

        # Migrate legacy hashes to bcrypt on successful login.
        if self._is_legacy_hash(user.hashed_password):
            user.hashed_password = self.hash_password(password)
            self._db.add(user)
            self._db.commit()
            self._db.refresh(user)

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
