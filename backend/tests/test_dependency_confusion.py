"""Tests for dependency confusion mitigation (TASK-037)."""
from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_pyproject_toml_is_non_publishable() -> None:
    """The package name is deliberately non-publishable."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    assert pyproject.exists()
    text = pyproject.read_text(encoding="utf-8")
    assert 'name = "taxflow-pro-private"' in text


def test_requirements_lock_exists_and_pins_dependencies() -> None:
    """requirements-lock.txt must exist and pin every top-level requirement."""
    lock = PROJECT_ROOT / "requirements-lock.txt"
    req = PROJECT_ROOT / "requirements.txt"
    assert lock.exists(), "requirements-lock.txt must exist"
    assert req.exists()

    lock_text = lock.read_text(encoding="utf-8").lower()
    missing = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("=")[0].split(">")[0].split("<")[0].strip().lower()
        # Strip extras (e.g. python-jose[cryptography] -> python-jose).
        pkg = pkg.split("[")[0].strip().lower()
        assert pkg, f"empty package name parsed from {line}"
        if pkg not in lock_text:
            missing.append(pkg)
    assert not missing, f"not pinned in requirements-lock.txt: {missing}"

    # Every line in the lock that names a package should pin an exact version.
    for line in lock_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"lock entry must pin exact version: {line}"


def test_namespace_policy_documented() -> None:
    """Internal namespace policy must be documented in BUILDER_MANUAL or README."""
    readme = PROJECT_ROOT / "README.md"
    builder = PROJECT_ROOT / "BUILDER_MANUAL.md"
    target = builder if builder.exists() else readme
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "taxflow_private" in text or "@taxflow/" in text, (
        "namespace policy not documented"
    )


def test_lockfile_mentions_namespace_policy() -> None:
    """The lockfile header should reference the dependency-confusion task."""
    lock = PROJECT_ROOT / "requirements-lock.txt"
    assert lock.exists()
    header = lock.read_text(encoding="utf-8").splitlines()[:10]
    header_text = "\n".join(header).lower()
    assert "task-037" in header_text or "dependency-confusion" in header_text
