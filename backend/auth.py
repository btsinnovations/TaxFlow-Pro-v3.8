"""Hybrid local auth for TaxFlow Pro v3.9.

Design rationale (from Stage 1 research):
- Single-tenant local desktop app with one local admin user.
- First boot: user supplies a master password. We derive or load `.local_secret`, create the local admin user with a bcrypt hash, and issue a JWT signed with `.local_secret`.
- Subsequent runs: POST /api/auth/login accepts OAuth2 form data or JSON, verifies the master password, and issues a JWT.
- Protected routes decode the JWT with `.local_secret` and look up the user in the local DB.
- If `.local_secret` is regenerated, previously issued tokens become invalid (acceptable for a local app).
- No external IdP, no cloud, no registration endpoint in production UI. A `/register` backdoor is retained for the existing test suite only.

Cryptography:
- bcrypt for password hashing.
- JWT (HS256) signed with the persisted `.local_secret`.
- Refresh tokens are opaque 64-byte URL-safe secrets; only SHA-256 hashes are stored in the database.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import socket
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models
from .local.crypto import (
    generate_local_secret_key,
    LocalCryptoManager,
    register_column_crypto_manager,
    clear_column_crypto_manager,
)
from .security.timing_safe import constant_time_verify_password
from .local.keyring_secret import (
    LOCAL_SECRET_FILE,
    retrieve_secret,
    store_secret,
    migrate_file_secret,
)


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("TAXFLOW_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("TAXFLOW_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
REFRESH_TOKEN_BYTES = 48  # 64 URL-safe chars


def _derive_username() -> str:
    """Derive the single local username from the Windows hostname if simple, otherwise 'local'."""
    hostname = socket.gethostname()
    simple = re.sub(r"[^a-zA-Z0-9-]", "", hostname).lower()[:20]
    if simple and len(simple) >= 2:
        return simple
    return "local"


def get_local_secret() -> str:
    """Load the local JWT signing secret.

    Preference order:
      1. Environment override `TAXFLOW_SECRET_KEY`.
      2. OS credential store via `keyring`.
      3. Fallback `.local_secret` file (headless/container deployments).

    If a `.local_secret` file exists but no keyring secret is present, the file
    is migrated into the credential store and then deleted.
    """
    env_secret = os.environ.get("TAXFLOW_SECRET_KEY")
    if env_secret:
        return env_secret

    # Migrate a pre-existing plaintext secret into the credential store. If the
    # credential store is unavailable the file is kept as the fallback.
    if LOCAL_SECRET_FILE.exists():
        migrated = migrate_file_secret()
        if migrated:
            return migrated
        return LOCAL_SECRET_FILE.read_text().strip()

    # Credential store is the default store after migration / first boot.
    secret = retrieve_secret()
    if secret:
        return secret

    # First boot on a fresh machine: generate, store in keyring, and write a
    # fallback file only if the credential store is unavailable.
    secret = generate_local_secret_key()
    store_secret(secret)
    return secret


SECRET_KEY = get_local_secret()


def refresh_secret_key() -> None:
    """Reload SECRET_KEY from the environment/file. Used by tests after monkeypatching."""
    global SECRET_KEY
    SECRET_KEY = get_local_secret()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Timing-safe password verification wrapper (delegates to security/timing_safe.py)."""
    return constant_time_verify_password(plain_password, hashed_password)


def create_access_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None,
    db: Optional[Session] = None,
) -> str:
    """Create a signed access token and, if a DB session is supplied, bind it
    to a server-side Session row for expiration tracking and revocation."""
    secret = get_local_secret()
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = secrets.token_urlsafe(32)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
        "type": "access",
    }
    token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    if db is not None:
        exp = payload["exp"]
        expires_dt = datetime.fromtimestamp(exp, tz=timezone.utc) if isinstance(exp, (int, float)) else exp
        _create_session_record(db, user_id, token, jti, expires_dt)
    return token


def _create_session_record(
    db: Session,
    user_id: int,
    token: str,
    jti: str,
    expires_at: datetime,
) -> models.Session:
    """Persist a server-side session row for an issued access token."""
    session = models.Session(
        token_hash=_hash_token(token),
        token_jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _lookup_session_by_token(db: Session, token: str) -> Optional[models.Session]:
    return db.query(models.Session).filter(models.Session.token_hash == _hash_token(token)).first()


def _session_is_valid(session: models.Session) -> bool:
    if session.revoked_at is not None:
        return False
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)


def decode_access_token(token: str, db: Optional[Session] = None) -> Optional[dict]:
    """Decode an access token and, if db is provided, enforce the revocation
    list and the server-side Session binding."""
    secret = get_local_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    if db is not None:
        jti = payload.get("jti")
        if jti and _is_token_revoked(db, jti):
            return None
        session = _lookup_session_by_token(db, token)
        if session is None or not _session_is_valid(session):
            return None
    return payload


def _hash_token(token: str) -> str:
    """Return the hex SHA-256 hash of an opaque token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_refresh_token_record(db: Session, user_id: int, family_id: Optional[str] = None) -> Tuple[str, models.RefreshToken]:
    """Generate an opaque refresh token and persist its hash in the database."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    family_id = family_id or uuid.uuid4().hex
    token = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
    token_hash = _hash_token(token)

    record = models.RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        family_id=family_id,
        expires_at=expires,
        created_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return token, record


def create_refresh_token(db: Session, user_id: int) -> str:
    """Create an opaque refresh token and persist its SHA-256 hash in the DB."""
    token, _record = _create_refresh_token_record(db, user_id)
    return token


def _lookup_refresh_token(db: Session, token: str) -> Optional[models.RefreshToken]:
    return db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == _hash_token(token)).first()


def _refresh_token_is_valid(record: models.RefreshToken) -> bool:
    if record.revoked_at is not None:
        return False
    # SQLite returns naive datetimes; normalize to UTC for comparison.
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)


def rotate_refresh_token(db: Session, old_refresh_token: str) -> Tuple[Optional[str], Optional[dict]]:
    """Validate a refresh token, mark it as replaced, and issue a rotated one in the same family.

    Returns ``(new_refresh_token, access_payload)`` on success, or
    ``(None, None)`` if the token is invalid, expired, or already revoked.

    If a token is reused after having been rotated (detected by ``replaced_by_token_hash``
    or ``revoked_at``), the entire family is revoked as a theft countermeasure.
    """
    record = _lookup_refresh_token(db, old_refresh_token)
    if record is None:
        return None, None

    if not _refresh_token_is_valid(record):
        # Reuse of an already-rotated/revoked token triggers family-wide revocation.
        revoke_refresh_family(db, old_refresh_token)
        return None, None

    new_token, new_record = _create_refresh_token_record(db, record.user_id, family_id=record.family_id)
    new_hash = new_record.token_hash

    now = datetime.now(timezone.utc)
    record.replaced_by_token_hash = new_hash
    record.revoked_at = now
    db.add(record)
    db.commit()

    access_token = create_access_token(record.user_id, db=db)
    access_payload = decode_access_token(access_token, db=db)
    return new_token, access_payload


def revoke_refresh_token(db: Session, token: str) -> bool:
    """Revoke a single refresh token by its plaintext value. Returns True if found and revoked."""
    record = _lookup_refresh_token(db, token)
    if record is None:
        return False
    if record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        db.add(record)
        db.commit()
    return True


def revoke_refresh_family(db: Session, token: str) -> int:
    """Revoke every token in the same family as the provided refresh token.

    Used for explicit logout and theft detection. Returns the number of tokens revoked.
    """
    record = _lookup_refresh_token(db, token)
    if record is None:
        return 0
    now = datetime.now(timezone.utc)
    rows = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.family_id == record.family_id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.revoked_at = now
        db.add(row)
    db.commit()
    return len(rows)


def _is_token_revoked(db: Session, jti: str) -> bool:
    return (
        db.query(models.RevokedToken)
        .filter(models.RevokedToken.jti == jti)
        .first()
        is not None
    )


def _revoke_access_token_by_jti(
    db: Session,
    jti: str,
    user_id: Optional[int] = None,
    expires_at: Optional[datetime] = None,
) -> Optional[models.RevokedToken]:
    existing = (
        db.query(models.RevokedToken)
        .filter(models.RevokedToken.jti == jti)
        .first()
    )
    if existing:
        return existing

    # Normalize naive datetimes to UTC for consistent comparison/cleanup.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    revoked = models.RevokedToken(
        jti=jti,
        user_id=user_id,
        token_type="access",
        expires_at=expires_at,
        revoked_at=datetime.now(timezone.utc),
    )
    db.add(revoked)
    db.commit()
    db.refresh(revoked)
    return revoked


def revoke_access_token(db: Session, token: str) -> Optional[models.RevokedToken]:
    """Revoke an access token by storing its jti and marking its Session row. Idempotent."""
    payload = decode_access_token(token)
    if payload is None:
        return None
    jti = payload.get("jti")
    if not jti:
        return None
    user_id = int(payload.get("sub")) if payload.get("sub") else None
    exp = payload.get("exp")
    expires_at = None
    if isinstance(exp, (int, float)):
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    # Also mark the server-side session revoked, when present.
    session = _lookup_session_by_token(db, token)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(session)
        db.commit()
    return _revoke_access_token_by_jti(db, jti, user_id=user_id, expires_at=expires_at)


def cleanup_expired_revoked_tokens(db: Session) -> int:
    """Delete revoked token records whose expiry has passed. Returns deleted count."""
    now = datetime.now(timezone.utc)
    # SQLite returns naive datetimes; normalize them before comparing.
    rows = (
        db.query(models.RevokedToken)
        .filter(models.RevokedToken.expires_at != None)
        .all()
    )
    deleted = 0
    for row in rows:
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            db.delete(row)
            deleted += 1
    if deleted:
        db.commit()
    return deleted


def is_first_boot(db: Session) -> bool:
    return db.query(models.User).first() is None


def _validate_keyfile(path: Path) -> None:
    """Ensure a keyfile exists and contains at least 32 bytes of entropy."""
    if not path.exists():
        raise ValueError(f"Keyfile not found: {path}")
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError("Keyfile must be at least 32 bytes")


def boot_local_admin(
    db: Session,
    master_password: str,
    keyfile_path: Optional[Path] = None,
) -> models.User:
    """Create the single local admin user on first boot.

    If a keyfile path is provided, the data-encryption key is derived from
    both the master password and the keyfile contents.
    """
    username = _derive_username()
    keyfile_path = Path(keyfile_path).resolve() if keyfile_path else None
    if keyfile_path is not None:
        _validate_keyfile(keyfile_path)
    crypto_manager = LocalCryptoManager.create(master_password, keyfile_path)
    user = models.User(
        username=username,
        email=None,
        hashed_password=hash_password(master_password),
        encryption_salt=crypto_manager.salt_b64,
        keyfile_path=str(keyfile_path) if keyfile_path else None,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    register_column_crypto_manager(user.id, master_password, user.encryption_salt, keyfile_path)
    return user


def authenticate_local_user(
    db: Session,
    password: str,
    keyfile_path: Optional[Path] = None,
) -> Optional[models.User]:
    """Verify master password (and optional keyfile) against the single local admin user."""
    user = db.query(models.User).first()
    # Always run bcrypt on a real hash, using a dummy when no user exists so the
    # failure timing and branch structure are identical.
    target_hash = user.hashed_password if user else None
    if not verify_password(password, target_hash):
        return None
    if user is None:
        return None

    # Ensure every login caches the column-encryption manager.
    if not user.encryption_salt:
        crypto_manager = LocalCryptoManager.create(password, keyfile_path)
        user.encryption_salt = crypto_manager.salt_b64
        db.add(user)
        db.commit()
        db.refresh(user)

    supplied = Path(keyfile_path).resolve() if keyfile_path else None
    configured = Path(user.keyfile_path).resolve() if user.keyfile_path else None
    if configured is not None:
        if supplied is None:
            raise ValueError("Keyfile required for this account; use /auth/login-json")
        if supplied != configured:
            raise ValueError("Keyfile mismatch")

    # If no keyfile is configured, ignore any supplied keyfile.
    register_column_crypto_manager(user.id, password, user.encryption_salt, configured)
    return user


def logout_local_user(db: Session, user: models.User) -> None:
    """Clear the in-memory column-encryption manager for a user."""
    clear_column_crypto_manager(user.id)
