"""Cryptographically secure random helpers.

All security-sensitive randomness (tokens, keys, salts, nonces, session IDs,
passwords) must use this module instead of the stdlib `random` module.
"""
from __future__ import annotations

import secrets
import string


def secure_token(nbytes: int = 32) -> str:
    """Return a hex-encoded random token."""
    return secrets.token_hex(nbytes)


def secure_urlsafe_token(nbytes: int = 32) -> str:
    """Return a URL-safe base64-encoded random token."""
    return secrets.token_urlsafe(nbytes)


def secure_random_int(min_val: int, max_val: int) -> int:
    """Return a random integer in [min_val, max_val] using secrets.randbelow."""
    if min_val >= max_val:
        raise ValueError("min_val must be less than max_val")
    return min_val + secrets.randbelow(max_val - min_val + 1)


def secure_alphanumeric(length: int = 16) -> str:
    """Return a random alphanumeric string for non-secret identifiers."""
    if length < 1:
        raise ValueError("length must be at least 1")
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
