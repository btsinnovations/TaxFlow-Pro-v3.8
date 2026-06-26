"""Production-mode detection and safety helpers.

This module is intentionally small: it centralizes the interpretation of the
``TAXFLOW_ENV`` / ``TAXFLOW_ENVIRONMENT`` variable so that routers, middleware,
and scripts can agree on whether the process is running in production.

Scaffolded for v3.11.5 (SEC.25). Full enforcement logic will be added in
subsequent commits.
"""
from __future__ import annotations

import os


def is_production() -> bool:
    """Return True if the active environment is production.

    Accepts ``TAXFLOW_ENV`` (short) or ``TAXFLOW_ENVIRONMENT`` (explicit).
    Any value other than ``production`` is treated as development.
    """
    env = os.environ.get("TAXFLOW_ENV", os.environ.get("TAXFLOW_ENVIRONMENT", "development")).lower()
    return env == "production"


def is_development() -> bool:
    """Return True if the active environment is development."""
    return not is_production()


def production_flag() -> str:
    """Return the raw, lower-cased environment string."""
    return os.environ.get("TAXFLOW_ENV", os.environ.get("TAXFLOW_ENVIRONMENT", "development")).lower()
