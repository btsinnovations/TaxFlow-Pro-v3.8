"""Local-first runtime settings and offline guards.

This module centralizes configuration for offline mode and provides helpers to
block or warn about cloud/API calls when running locally.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from backend.local.secrets_loader import get_secret


# SQLCipher / local encryption settings (TASK-038 / 3.3)
# The master password is the only required secret; the salt is public.
# Secrets file takes precedence over environment variables.
SQLCIPHER_PASSWORD = get_secret("TAXFLOW_DB_PASSWORD", os.environ.get("TAXFLOW_DB_PASSWORD", ""))
SQLCIPHER_KEYFILE = get_secret("TAXFLOW_DB_KEYFILE", os.environ.get("TAXFLOW_DB_KEYFILE", None))
SQLCIPHER_KEYRING_TOKEN = get_secret("TAXFLOW_DB_KEYRING_TOKEN", os.environ.get("TAXFLOW_DB_KEYRING_TOKEN", None))


# Local storage root — database, models, backups, settings all live here.
# By default uses the project root, but can be overridden.
LOCAL_ROOT = Path(
    os.environ.get("TAXFLOW_LOCAL_ROOT", ".")
).resolve()


def get_local_path(name: str) -> Path:
    """Return a path inside the local root, creating parent dirs on demand."""
    path = LOCAL_ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# Runtime mode flags
class RuntimeMode:
    OFFLINE = "offline"
    ONLINE = "online"


# Defaults to offline unless explicitly opted in.
RUNTIME_MODE = os.environ.get("TAXFLOW_RUNTIME_MODE", RuntimeMode.OFFLINE)

# Environment classification: development | production
ENVIRONMENT = os.environ.get("TAXFLOW_ENVIRONMENT", "development").lower()


def is_offline() -> bool:
    """Return True if the app is configured to operate without any cloud services."""
    return RUNTIME_MODE.lower() == RuntimeMode.OFFLINE


def is_online() -> bool:
    return not is_offline()


def require_offline() -> None:
    """Raise if the runtime is not in offline mode.

    Call at startup for features that must not talk to the network.
    """
    if not is_offline():
        raise RuntimeError("Expected offline runtime mode")


def guard_cloud_call(feature: str) -> None:
    """Raise a clear error when a cloud/API call is attempted in offline mode."""
    if is_offline():
        raise RuntimeError(
            f"Cloud/API call blocked in offline mode: {feature}. "
            "Set TAXFLOW_RUNTIME_MODE=online to allow this."
        )


# Feature flags: these can be toggled without code changes.
FEATURE_FLAGS = {
    "plaid": False,
    "stripe": False,
    "smtp_email": False,
    "oauth_login": False,
    "telemetry": False,
    "auto_update_check": False,
    "cloud_ml": False,
}


def feature_enabled(name: str) -> bool:
    """Check whether a cloud-dependent feature is enabled."""
    return FEATURE_FLAGS.get(name, False)


def guard_feature(name: str) -> None:
    """Raise if a cloud-dependent feature is disabled or unavailable."""
    if not feature_enabled(name):
        raise RuntimeError(f"Feature '{name}' is disabled in local/offline mode.")


# Single-user default mode (TASK-038.14)
TAXFLOW_SINGLE_USER = os.environ.get("TAXFLOW_SINGLE_USER", "true").lower() in ("1", "true", "yes")


def is_single_user() -> bool:
    """Return True when the app should operate as a single local user."""
    # Read dynamically so tests can toggle the flag without reloading modules.
    return os.environ.get("TAXFLOW_SINGLE_USER", "true").lower() in ("1", "true", "yes")
