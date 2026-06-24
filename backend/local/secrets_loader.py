"""Load sensitive key=value pairs from a file outside version control.

Used by backend/local/settings.py and backend/database.py so that secrets
like DATABASE_URL passwords, SQLCipher passwords, and keyfile paths can be
kept out of the process environment on shared machines.
"""
from __future__ import annotations

import os
from pathlib import Path


SECRETS_FILE_ENV = "TAXFLOW_SECRETS_FILE"


def load_secrets_file() -> dict[str, str]:
    """Load key=value pairs from the path in TAXFLOW_SECRETS_FILE, if set.

    Returns an empty dict if the env var is unset or the file is missing.
    Lines starting with '#' and empty lines are ignored. Values are not
    unquoted or expanded.
    """
    path_str = os.environ.get(SECRETS_FILE_ENV)
    if not path_str:
        return {}
    path = Path(path_str).expanduser()
    if not path.exists():
        return {}

    secrets: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        secrets[key.strip()] = value.strip()
    return secrets


# Module-level singleton; imported modules read this at import time.
_SECRETS = load_secrets_file()


def _reload_secrets() -> dict[str, str]:
    """Reload secrets from disk; used by tests after changing TAXFLOW_SECRETS_FILE."""
    global _SECRETS
    _SECRETS = load_secrets_file()
    return _SECRETS


def get_secret(key: str, env_default: str | None = None) -> str | None:
    """Return a secret from the secrets file, falling back to an env var.

    The secrets file takes precedence so that a value stored on disk can
    override an env var without exposing it to /proc/<pid>/environ.
    """
    return _SECRETS.get(key, os.environ.get(key, env_default))


def redact_url(url: str) -> str:
    """Remove the password component from a URL before logging."""
    import re
    return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", url)
