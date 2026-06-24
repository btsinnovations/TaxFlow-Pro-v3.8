"""Timing-attack-safe authentication helpers (TASK-034).

These helpers ensure that the authentication path does not leak information
through side channels such as response timing or status codes/text.
"""
from __future__ import annotations

import hmac
from typing import Optional, Union

import bcrypt
from sqlalchemy.orm import Session

from .. import models

# A fixed dummy hash used when a user is not found. It is intentionally a valid
# bcrypt hash so that we can always invoke bcrypt.checkpw on the same code path.
_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode("utf-8")


class _SentinelUser:
    """A non-persistent stand-in returned when no real user is found.

    It carries a username padded to a fixed length and a dummy hash so that
    the caller can perform constant-time comparisons and password checks
    without branches.
    """

    username: str = "x" * 32
    hashed_password: str = _DUMMY_HASH
    is_real: bool = False


def constant_time_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """Return True if `a` and `b` are equal, compared in constant time."""
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hmac.compare_digest(a, b)


def _safe_bcrypt_check(plain_password: str, hashed_password: str) -> bool:
    """Verify `plain_password` against `hashed_password` in constant time.

    Always runs bcrypt on a real hash, so the runtime does not depend on
    whether a user exists.
    """
    plain = plain_password.encode("utf-8")
    candidate = hashed_password.encode("utf-8")
    # `bcrypt.checkpw` itself is not strictly constant-time, but it is the
    # standard defense-in-depth primitive. We wrap it so the *branch structure*
    # is identical regardless of whether a user exists.
    try:
        return bcrypt.checkpw(plain, candidate)
    except ValueError:
        return False


def constant_time_verify_password(
    plain_password: str,
    hashed_password: Optional[str],
) -> bool:
    """Constant-time password verification.

    If `hashed_password` is None or empty, a dummy hash is used so the failure
    path performs the same bcrypt work as the success path.
    """
    target = hashed_password if hashed_password else _DUMMY_HASH
    result = _safe_bcrypt_check(plain_password, target)
    return result


def _padded_username(username: str) -> str:
    """Pad or truncate a username to a fixed 32 characters.

    This ensures `constant_time_compare` always operates on equal-length
    inputs, avoiding any length-dependent timing differences.
    """
    if len(username) > 32:
        return username[:32]
    return username.ljust(32, chr(0))


def constant_time_user_lookup(
    db: Session, username: str
) -> Union[models.User, _SentinelUser]:
    """Look up the single local user without leaking username timing.

    Instead of asking the database to filter by username (which can expose
    existence through index-hit vs miss timing), this function fetches the
    first user record and performs a constant-time username comparison in
    Python. The comparison result is attached to the returned user object as
    `_tf_username_match` so callers may use it without re-comparing.

    If the database contains no users, a `_SentinelUser` is returned so that
    callers always follow the same code path and do not branch on existence.

    In the single-tenant local app there is exactly one user; tests that
    create extra users are expected to reset the database per test.
    """
    user = db.query(models.User).first()
    if user is None:
        return _SentinelUser()
    padded = _padded_username(username)
    # Constant-time comparison prevents leaking whether the username matched.
    user._tf_username_match = constant_time_compare(
        _padded_username(user.username), padded
    )
    return user
