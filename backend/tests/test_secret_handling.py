"""Tests for secrets-file support and URL redaction (TASK-036)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.local.secrets_loader import load_secrets_file, redact_url, get_secret, SECRETS_FILE_ENV


@pytest.fixture
def temp_secrets_file(tmp_path: Path):
    """Create a temporary secrets file and set the env var."""
    path = tmp_path / "test.secrets"
    path.write_text(
        "DATABASE_URL=postgresql://dbuser:dbpass@localhost/taxflow\n"
        "TAXFLOW_DB_PASSWORD=super_secret_password\n"
        "TAXFLOW_DB_KEYFILE=/secure/keyfile.bin\n"
        "# comment line\n"
        "TAXFLOW_DB_KEYRING_TOKEN=keyring-token-123\n",
        encoding="utf-8",
    )
    old_env = os.environ.get(SECRETS_FILE_ENV)
    os.environ[SECRETS_FILE_ENV] = str(path)
    yield path
    if old_env is None:
        os.environ.pop(SECRETS_FILE_ENV, None)
    else:
        os.environ[SECRETS_FILE_ENV] = old_env


def test_load_secrets_file_parses_key_value_pairs(temp_secrets_file: Path) -> None:
    """TODO: Jane — assert secrets file is parsed into expected dict."""
    secrets = load_secrets_file()
    assert "DATABASE_URL" in secrets
    assert "TAXFLOW_DB_PASSWORD" in secrets
    assert secrets["TAXFLOW_DB_KEYFILE"] == "/secure/keyfile.bin"


def test_get_secret_prefers_secrets_file_over_env(temp_secrets_file: Path, monkeypatch) -> None:
    """TODO: Jane — assert secrets file value overrides env value."""
    from backend.local import secrets_loader
    secrets_loader._reload_secrets()
    monkeypatch.setenv("DATABASE_URL", "env-value")
    assert get_secret("DATABASE_URL", "fallback") == "postgresql://dbuser:dbpass@localhost/taxflow"


def test_redact_url_obscures_password() -> None:
    """TODO: Jane — assert password in URL is replaced with ***."""
    url = "postgresql://dbuser:secret123@localhost/taxflow"
    redacted = redact_url(url)
    assert "secret123" not in redacted
    assert "***" in redacted
    assert redacted == "postgresql://dbuser:***@localhost/taxflow"


def test_redact_url_handles_url_without_password() -> None:
    """TODO: Jane — assert URL without password is unchanged."""
    url = "postgresql://dbuser@localhost/taxflow"
    assert redact_url(url) == url
