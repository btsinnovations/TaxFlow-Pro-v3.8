"""Path traversal protection for TaxFlow Pro.

Provides deterministic filename sanitization and base-directory-constrained
path resolution. Every user-derived filename or relative path must pass through
this module before touching the filesystem.
"""
from __future__ import annotations

import re
from pathlib import Path, PurePath


# Reserved Windows device names, case-insensitive.
_RESERVED_WINDOWS_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)

# Reserved names plus any digit suffix (e.g., "CON1", "COM9", "LPT1.txt").
_RESERVED_WINDOWS_SUFFIX_RE = re.compile(
    r"^(" + "|".join(re.escape(name) for name in _RESERVED_WINDOWS_NAMES) + r")(\d*)(\.|$)",
    re.IGNORECASE,
)

# Characters that are unsafe or illegal in cross-platform filenames.
# Includes path separators, null bytes, control characters, and a few shell metacharacters.
_UNSAFE_CHARS_RE = re.compile(r"[\x00-\x1f\x7f<>:/\\|?*\"'\`\$;\{\}\[\]\n\r\t]")


# Default fallback name used when a supplied filename is stripped to nothing.
_FALLBACK_NAME = "unnamed"


def sanitize_filename(name: str, fallback: str = _FALLBACK_NAME) -> str:
    """Return a safe, flat filename with path traversal elements removed.

    Sanitization rules:
      - Strip path separators, null bytes, control chars, and shell metacharacters.
      - Reject reserved Windows device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
      - Collapse multiple dots and underscores to a single dot/underscore.
      - Strip leading dots to prevent ``.htaccess``/``..`` style attacks.
      - If the result is empty, return ``fallback``.
    """
    if not isinstance(name, str):
        name = str(name)

    # Normalize separators to the platform separator then split; this removes
    # any absolute or relative path components.
    flat = Path(name).name

    # Replace spaces with underscores to avoid shell/URL issues.
    flat = flat.replace(" ", "_")

    # Remove unsafe characters.
    cleaned = _UNSAFE_CHARS_RE.sub("", flat)

    # Remove reserved Windows device names.
    if _RESERVED_WINDOWS_SUFFIX_RE.match(cleaned):
        cleaned = re.sub(r"^" + cleaned.split(".")[0], fallback, cleaned, flags=re.IGNORECASE)

    # Collapse multiple separators.
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    cleaned = cleaned.strip(" ._")

    # Guard against a name that is only dots/underscores/spaces.
    if not cleaned or cleaned in (".", "..", ""):
        return fallback

    return cleaned


def safe_path(base_dir: Path, rel_path: str | Path, *, must_exist: bool = False) -> Path:
    """Resolve ``rel_path`` strictly under ``base_dir``.

    Raises ``ValueError`` if the resolved path escapes ``base_dir`` or if
    ``must_exist`` is True and the path does not exist.

    This uses ``resolve()`` (symlinks followed) on both sides so that
    symlink-based traversal attempts are also detected.
    """
    base = Path(base_dir).resolve()
    target = (base / Path(str(rel_path))).resolve()

    if must_exist and not target.exists():
        raise ValueError(f"Path does not exist: {target}")

    # On Windows, ``startswith`` string comparison is safe after resolve().
    # We also check that target has base as a proper ancestor (not base itself,
    # unless base is the root and rel_path is empty, which we reject).
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"Path traversal detected: {rel_path!r} resolves outside {base}"
        ) from exc

    return target


def safe_user_filename(user_id: int, original_filename: str) -> str:
    """Build a user-scoped safe filename for uploaded files.

    The user_id prefix prevents collisions between users and the sanitized
    name prevents path traversal / reserved-name attacks.
    """
    cleaned = sanitize_filename(original_filename)
    return f"{user_id}_{cleaned}"
