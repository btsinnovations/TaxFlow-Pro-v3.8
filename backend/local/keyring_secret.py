"""OS credential-store wrapper for the local JWT signing secret.

`keyring` is the default backend. If it is unavailable or raises, we fall back
to the plaintext `.local_secret` file so headless/container deployments keep
working.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

try:
    import keyring
except Exception:  # pragma: no cover - handled below
    keyring = None  # type: ignore

from .crypto import generate_local_secret_key
from .settings import get_local_path

logger = logging.getLogger(__name__)

# Resolve the local secret file inside the configured local root. On a fresh
# first boot this directory may not exist yet, so we ensure parents on write.
DEFAULT_LOCAL_SECRET_FILE = get_local_path(".local_secret")
LOCAL_SECRET_FILE = Path(os.environ.get("TAXFLOW_LOCAL_SECRET_FILE", str(DEFAULT_LOCAL_SECRET_FILE)))
DEFAULT_SERVICE = "TaxFlow-Pro"
DEFAULT_ACCOUNT = "local_secret"


def _read_file_secret() -> Optional[str]:
    if not LOCAL_SECRET_FILE.exists():
        return None
    try:
        return LOCAL_SECRET_FILE.read_text().strip()
    except Exception as exc:
        logger.warning("Failed to read fallback secret file %s: %s", LOCAL_SECRET_FILE, exc)
        return None


def _set_secret_file_permissions(path: Path) -> None:
    """Restrict secret file access to the file owner only.

    POSIX: mode 0o600. Windows: inheritance stripped from parent ACL; current
    user gets full control; builtin Users/Everyone are removed when possible.
    """
    if os.name == "posix":
        import stat
        try:
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception as exc:
            logger.warning("Failed to chmod secret file %s: %s", path, exc)
    elif os.name == "nt":
        # We try to set an owner-only DACL using pywin32 if available.
        try:
            import win32security  # type: ignore # noqa: F401
            import ntsecuritycon as con  # type: ignore # noqa: F401
        except Exception:
            logger.debug("pywin32 unavailable; skipping Windows ACL hardening")
            return
        try:
            import win32api
            import win32security
            import ntsecuritycon as con
            from pathlib import PureWindowsPath

            win_path = str(PureWindowsPath(path))
            sd = win32security.GetFileSecurity(
                win_path, win32security.DACL_SECURITY_INFORMATION
            )
            dacl = win32security.ACL()
            import win32api
            username = win32api.GetUserName()
            user, _domain, _account_type = win32security.LookupAccountName("", username)
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE | con.DELETE,
                user,
            )
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                win_path, win32security.DACL_SECURITY_INFORMATION, sd
            )
        except Exception as exc:
            logger.warning("Failed to harden Windows ACL on secret file: %s", exc)


def _write_file_secret(secret: str) -> None:
    try:
        LOCAL_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_SECRET_FILE.write_text(secret)
        _set_secret_file_permissions(LOCAL_SECRET_FILE)
    except Exception as exc:
        logger.warning("Failed to write fallback secret file %s: %s", LOCAL_SECRET_FILE, exc)


def _delete_file_secret() -> None:
    try:
        if LOCAL_SECRET_FILE.exists():
            LOCAL_SECRET_FILE.unlink()
    except Exception as exc:
        logger.warning("Failed to delete fallback secret file %s: %s", LOCAL_SECRET_FILE, exc)


def store_secret(
    secret: str,
    service: str = DEFAULT_SERVICE,
    account: str = DEFAULT_ACCOUNT,
) -> bool:
    """Store secret in the OS credential store, falling back to file.

    Returns True if the secret was stored in the keyring, False if the file
    fallback was used.
    """
    try:
        if keyring is None:
            raise RuntimeError("keyring module not available")
        keyring.set_password(service, account, secret)
        return True
    except Exception as exc:
        logger.debug("Keyring store failed, using file fallback: %s", exc)
        _write_file_secret(secret)
        return False


def retrieve_secret(
    service: str = DEFAULT_SERVICE,
    account: str = DEFAULT_ACCOUNT,
) -> Optional[str]:
    """Retrieve secret from OS credential store, falling back to file."""
    try:
        if keyring is None:
            raise RuntimeError("keyring module not available")
        secret = keyring.get_password(service, account)
        if secret:
            return secret
    except Exception as exc:
        logger.debug("Keyring retrieve failed, using file fallback: %s", exc)
    return _read_file_secret()


def delete_secret(
    service: str = DEFAULT_SERVICE,
    account: str = DEFAULT_ACCOUNT,
) -> None:
    """Delete secret from OS credential store and from file fallback."""
    try:
        if keyring is not None:
            keyring.delete_password(service, account)
    except Exception as exc:
        logger.debug("Keyring delete failed: %s", exc)
    _delete_file_secret()


def migrate_file_secret(
    service: str = DEFAULT_SERVICE,
    account: str = DEFAULT_ACCOUNT,
) -> Optional[str]:
    """If the fallback secret file exists, move its contents into the keyring.

    The file is deleted only after the credential store successfully receives
    the secret. If the keyring is unavailable, the plaintext file is kept as
    the fallback.

    Returns the migrated secret or None if no file existed.
    """
    secret = _read_file_secret()
    if not secret:
        return None
    if store_secret(secret, service, account):
        _delete_file_secret()
    return secret
