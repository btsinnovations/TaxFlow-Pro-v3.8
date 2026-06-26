"""Stub tests for production-mode behavior.

Expected coverage (v3.11.5):
- ``TAXFLOW_ENV=production`` sets ``local_settings.is_production()`` to True.
- ``/api/tests/`` router is absent in production.
- Debug-only middleware/routes are absent in production.
- Health endpoints report ``production_mode: true`` in production.

These tests currently import the helpers without making assertions so that the
stub scaffolding can land before full logic is implemented.
"""
from __future__ import annotations


# TODO(v3.11.5): import backend.local.settings and backend.security.production_mode
# once the full production-mode contract is wired.


def test_production_mode_stub_imports():
    """Placeholder that ensures the production-mode module imports cleanly."""
    from backend.security import production_mode

    assert hasattr(production_mode, "is_production")
    assert hasattr(production_mode, "is_development")


def test_production_mode_defaults_to_development():
    """Placeholder confirming the default environment is development."""
    from backend.security.production_mode import is_development

    assert is_development() is True
