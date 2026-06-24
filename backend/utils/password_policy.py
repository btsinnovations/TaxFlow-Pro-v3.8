"""Master-password policy for TaxFlow Pro local boot/registration.

Implements the v3.9.1 SEC-02 requirements without adding external dependencies.
Entropy is computed with Shannon entropy over the character classes present in
the password. This is intentionally simpler than `zxcvbn` (which is not in
requirements.txt) and errs conservative.
"""
from __future__ import annotations

import hashlib
import math
import re

from ..security.breach_bloom import is_breached


COMMON_PASSWORDS = frozenset({
    "password", "password1", "password12", "password123", "password1234",
    "password12345", "password123456", "password1234567", "password12345678",
    "qwerty", "qwerty123", "qwertyuiop", "123456", "12345678", "1234567890",
    "123456789", "1234567890", "111111", "123123", "abc123", "letmein",
    "welcome", "monkey", "dragon", "master", "sunshine", "princess",
    "admin", "admin123", "root", "toor", "login", "user", "test", "guest",
    "changeme", "default", "taxflow", "taxflow123", "taxflow2026",
    "qwerty12345", "iloveyou", "trustno1", "baseball", "football",
    "superman", "batman", "harley", "hunter", "ranger", "thomas",
    "robert", "michael", "jordan", "maggie", "buster", "daniel",
    "andrew", "joshua", "joshua123", "josh", "josh123", "james",
})


_MIN_LENGTH = 12
_MIN_ENTROPY = 50.0


def _shannon_entropy(password: str) -> float:
    if not password:
        return 0.0
    counts: dict[str, int] = {}
    for ch in password:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(password)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy * length


def _password_classes(password: str) -> int:
    classes = 0
    if re.search(r"[a-z]", password):
        classes += 1
    if re.search(r"[A-Z]", password):
        classes += 1
    if re.search(r"\d", password):
        classes += 1
    if re.search(r"[^A-Za-z0-9]", password):
        classes += 1
    return classes


def _crack_entropy(password: str) -> float:
    """Estimate bits of entropy based on character set size and length.

    This is a conservative lower-bound estimate that treats low-diversity
    passwords as weaker than a true Shannon calculation would.
    """
    classes = _password_classes(password)
    pool = {1: 26, 2: 30, 3: 50, 4: 78}.get(classes, 78)
    entropy = len(password) * math.log2(pool)
    if classes == 1:
        entropy *= 0.45
    elif classes == 2:
        entropy *= 0.65
    return entropy


def _zxcvbn_score(password: str) -> int:
    """Return a 0-4 score if zxcvbn is installed, else 0."""
    try:
        import zxcvbn  # type: ignore
        return zxcvbn.zxcvbn(password).get("score", 0)
    except Exception:
        return 0


def validate_master_password(password: str, username: str | None = None) -> list[str]:
    """Return a list of failed policy checks. Empty list means acceptable."""
    failures: list[str] = []
    if password is None:
        password = ""

    if len(password) < _MIN_LENGTH:
        failures.append(f"Password must be at least {_MIN_LENGTH} characters long.")

    entropy = _crack_entropy(password)
    if entropy < _MIN_ENTROPY:
        failures.append(
            f"Password entropy is {entropy:.1f} bits; minimum required is {_MIN_ENTROPY:.0f} bits."
        )

    low = password.lower()
    if "password" in low:
        failures.append("Password must not contain the word 'password'.")

    if is_breached(password):
        failures.append("Password appears in a known breach database.")

    if username and username.lower() in low:
        failures.append("Password must not contain the username.")

    if low in COMMON_PASSWORDS or password.lower() in COMMON_PASSWORDS:
        failures.append("Password is too common or easily guessed.")

    if _zxcvbn_score(password) < 3:
        # Only add zxcvbn failure when zxcvbn is actually installed.
        try:
            import zxcvbn  # type: ignore  # noqa: F401
            failures.append("Password zxcvbn score is below 3; choose a stronger passphrase.")
        except Exception:
            pass

    return failures
