"""SQLCipher-backed SQLite engine for TaxFlow Pro local-first encryption.

Design goals:
- No plaintext key material on disk.
- The master password is the only human-required secret.
- Key derivation uses Argon2id with a per-database salt stored in a public
  sidecar file next to the database (e.g., ``taxflow.db.salt``).
- Optional keyfile or OS-keyring token can be mixed in as a second factor.
- The derived 256-bit raw key is passed to SQLCipher as a hex literal and lives
  only in memory.
- Existing plain SQLite databases can be migrated into SQLCipher by attaching
  the plaintext DB to a SQLCipher connection and copying its contents.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import stat
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Argon2id parameters tuned for interactive master-password derivation.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 65536  # 64 MB
ARGON2_PARALLELISM = 1
SALT_BYTES = 16

# SQLCipher is provided by sqlcipher3-wheels, a DB-API 2.0 drop-in for sqlite3.
SQLCIPHER_AVAILABLE = False
try:
    from sqlcipher3 import dbapi2 as sqlcipher  # type: ignore
    SQLCIPHER_AVAILABLE = True
except Exception as exc:  # pragma: no cover - platform/build dependent
    logger.warning("sqlcipher3 is not installed; SQLCipher support disabled: %s", exc)
    sqlcipher = None  # type: ignore


class SQLCipherError(Exception):
    pass


def is_sqlcipher_available() -> bool:
    return SQLCIPHER_AVAILABLE


def _derive_password_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password and salt using Argon2id."""
    if len(salt) < SALT_BYTES:
        raise SQLCipherError("Salt must be at least 16 bytes")
    kdf = Argon2id(
        salt=salt,
        length=32,
        iterations=ARGON2_TIME_COST,
        lanes=ARGON2_PARALLELISM,
        memory_cost=ARGON2_MEMORY_COST_KIB,
    )
    return kdf.derive(password.encode("utf-8"))


def _hash_file_or_bytes(data: bytes) -> bytes:
    """Return a 32-byte SHA-3_256 digest of the provided key material."""
    return hashlib.sha3_256(data).digest()


def _combine_key_material(password_key: bytes, extras: list[bytes]) -> bytes:
    """Mix password-derived key with optional keyfile/keyring factors."""
    if not extras:
        return password_key
    material = password_key
    for extra in extras:
        material += extra
    return HKDF(
        algorithm=hashes.SHA3_256(),
        length=32,
        salt=None,
        info=b"taxflow-sqlcipher-v1",
    ).derive(material)


def _format_pragma_key(raw_key: bytes) -> str:
    """Return a SQLCipher PRAGMA key literal for a raw 256-bit key.

    This build of sqlcipher3-wheels rejects the raw-key blob syntax
    ``x'...'`` unless it is passed as a double-quoted string literal. We
    therefore return the literal wrapped in double quotes so the driver
    binds it correctly while SQLCipher still interprets the ``x'...'``
    prefix as a 256-bit raw key.
    """
    if len(raw_key) != 32:
        raise SQLCipherError("SQLCipher raw key must be 32 bytes")
    return f'"x\'{raw_key.hex()}\'"'


def _salt_path(db_path: Path) -> Path:
    """Sidecar path that stores the public Argon2 salt."""
    return Path(str(db_path) + ".salt")


def read_salt(db_path: Path) -> Optional[bytes]:
    """Read the public Argon2 salt sidecar for a SQLCipher database."""
    path = _salt_path(db_path)
    if not path.exists():
        return None
    try:
        return base64.b64decode(path.read_text().strip())
    except Exception as exc:
        raise SQLCipherError(f"Failed to read salt sidecar {path}") from exc


def write_salt(db_path: Path, salt: bytes) -> None:
    """Persist the public Argon2 salt sidecar and restrict its permissions."""
    path = _salt_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(base64.b64encode(salt).decode("ascii"))
    try:
        if os.name == "posix":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def get_or_create_salt(db_path: Path) -> bytes:
    """Return an existing salt or generate and persist a new one."""
    salt = read_salt(db_path)
    if salt is not None:
        return salt
    salt = secrets.token_bytes(SALT_BYTES)
    write_salt(db_path, salt)
    return salt


def derive_sqlcipher_key(
    password: str,
    db_path: Path,
    keyfile_path: Optional[Path] = None,
    keyring_token: Optional[bytes] = None,
) -> str:
    """Derive the SQLCipher ``PRAGMA key`` string for a database.

    The returned string is ready to be interpolated into ``PRAGMA key = ...``
    as a raw hex literal.
    """
    salt = get_or_create_salt(db_path)
    password_key = _derive_password_key(password, salt)

    extras: list[bytes] = []
    if keyfile_path is not None:
        if not keyfile_path.exists():
            raise SQLCipherError(f"Keyfile not found: {keyfile_path}")
        data = keyfile_path.read_bytes()
        if len(data) < 32:
            raise SQLCipherError("Keyfile must be at least 32 bytes")
        extras.append(_hash_file_or_bytes(data))
    if keyring_token is not None:
        if len(keyring_token) < 16:
            raise SQLCipherError("Keyring token must be at least 16 bytes")
        extras.append(_hash_file_or_bytes(keyring_token))

    raw_key = _combine_key_material(password_key, extras)
    return _format_pragma_key(raw_key)


def _set_key_on_connect(
    dbapi_conn,
    connection_record,
    password: str,
    db_path: Path,
    keyfile_path: Optional[Path],
    keyring_token: Optional[bytes],
):
    """SQLAlchemy engine event listener that unlocks SQLCipher on connect."""
    try:
        key_str = derive_sqlcipher_key(password, db_path, keyfile_path, keyring_token)
        cursor = dbapi_conn.cursor()
        cursor.execute(f"PRAGMA key = {key_str}")
        # Quick sanity check: a wrong key surfaces on the first actual page read.
        cursor.execute("SELECT count(*) FROM sqlite_master")
        cursor.close()
    except Exception as exc:
        logger.error("Failed to unlock SQLCipher database %s: %s", db_path, exc)
        raise SQLCipherError("Failed to unlock SQLCipher database") from exc


def _extract_db_path(db_url: str) -> Path:
    """Parse a SQLite-style URL and return the absolute filesystem path."""
    if db_url.startswith("sqlite:///"):
        rel = db_url[len("sqlite:///"):]
        return Path(rel).resolve()
    if db_url.startswith("sqlcipher:///"):
        rel = db_url[len("sqlcipher:///"):]
        return Path(rel).resolve()
    raise SQLCipherError(f"Unsupported SQLCipher database URL: {db_url}")


def create_sqlcipher_engine(
    db_url: str,
    password: str,
    keyfile_path: Optional[Path] = None,
    keyring_token: Optional[bytes] = None,
):
    """Create a SQLAlchemy engine backed by SQLCipher.

    ``db_url`` may use either ``sqlite:///`` or ``sqlcipher:///`` scheme.
    The actual file path is used to locate (or create) the public salt sidecar.
    """
    if not SQLCIPHER_AVAILABLE:
        raise SQLCipherError(
            "sqlcipher3 is not installed; install sqlcipher3-wheels to enable SQLCipher"
        )
    if not password:
        raise SQLCipherError("SQLCipher requires a non-empty master password")

    db_path = _extract_db_path(db_url)
    # Ensure the salt sidecar exists before any connection attempts.
    get_or_create_salt(db_path)

    from sqlalchemy import create_engine, event

    # sqlcipher3.dbapi2 is a drop-in replacement for sqlite3.
    engine = create_engine(
        "sqlite:///" + str(db_path),
        module=sqlcipher,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    event.listen(
        engine,
        "connect",
        lambda dbapi_conn, connection_record: _set_key_on_connect(
            dbapi_conn,
            connection_record,
            password,
            db_path,
            keyfile_path,
            keyring_token,
        ),
    )
    return engine


def migrate_plaintext_to_sqlcipher(
    plain_db_path: Path,
    encrypted_db_path: Path,
    password: str,
    keyfile_path: Optional[Path] = None,
    keyring_token: Optional[bytes] = None,
):
    """Migrate an existing plain SQLite database into a new SQLCipher database.

    Uses SQLCipher's ``sqlcipher_export()`` to copy schema and data. The
    plaintext database is left untouched.
    """
    if not SQLCIPHER_AVAILABLE:
        raise SQLCipherError("sqlcipher3 is not installed")
    if encrypted_db_path.exists():
        raise SQLCipherError(f"Destination already exists: {encrypted_db_path}")
    if not plain_db_path.exists():
        raise SQLCipherError(f"Source database not found: {plain_db_path}")

    encrypted_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the encrypted DB with the desired key.
    enc_url = f"sqlite:///{encrypted_db_path}"
    enc_engine = create_sqlcipher_engine(enc_url, password, keyfile_path, keyring_token)
    with enc_engine.connect() as conn:
        # Attach the plaintext database with KEY '' to force unencrypted mode.
        conn.exec_driver_sql("ATTACH DATABASE ? AS plaintext KEY ''", (str(plain_db_path),))
        conn.exec_driver_sql("SELECT sqlcipher_export('main', 'plaintext')")
        conn.exec_driver_sql("DETACH DATABASE plaintext")
        conn.commit()
    enc_engine.dispose()


def rekey_sqlcipher_database(
    db_path: Path,
    old_password: str,
    new_password: str,
    old_keyfile_path: Optional[Path] = None,
    new_keyfile_path: Optional[Path] = None,
    old_keyring_token: Optional[bytes] = None,
    new_keyring_token: Optional[bytes] = None,
):
    """Change the SQLCipher key for an existing database.

    This re-encrypts every database page. The salt sidecar is left unchanged;
    only the raw key derived from the password (+ optional factors) changes.
    """
    old_key = derive_sqlcipher_key(old_password, db_path, old_keyfile_path, old_keyring_token)
    new_key = derive_sqlcipher_key(new_password, db_path, new_keyfile_path, new_keyring_token)

    if not SQLCIPHER_AVAILABLE:
        raise SQLCipherError("sqlcipher3 is not installed")

    conn = sqlcipher.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA key = {old_key}")
        cur.execute("SELECT count(*) FROM sqlite_master")
        cur.execute(f"PRAGMA rekey = {new_key}")
        conn.commit()
        cur.close()
    finally:
        conn.close()


def generate_keyfile(path: Path, size: int = 64) -> Path:
    """Generate a cryptographically random keyfile and write it to disk."""
    if size < 32:
        raise ValueError("Keyfile size must be at least 32 bytes")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(secrets.token_bytes(size))
    try:
        if os.name == "posix":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    return path


def generate_keyring_token(size: int = 32) -> bytes:
    """Generate a random token suitable for use as an OS-keyring second factor."""
    if size < 16:
        raise ValueError("Keyring token size must be at least 16 bytes")
    return secrets.token_bytes(size)
