"""Centralized safe YAML loading helpers.

Uses CSafeLoader when available and SafeLoader otherwise. Never use yaml.Loader
or yaml.UnsafeLoader for user-supplied or project configuration YAML.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # pragma: no cover
    from yaml import SafeLoader  # type: ignore[assignment]

import yaml


class YAMLError(Exception):
    """Raised when a YAML file cannot be parsed safely."""
    pass


def safe_load_yaml(text: str) -> Any:
    """Parse YAML text using only safe constructors."""
    try:
        return yaml.load(text, Loader=SafeLoader)
    except yaml.YAMLError as exc:
        raise YAMLError(f"Invalid YAML: {exc}") from exc


def safe_load_yaml_file(path: Path | str) -> Any:
    """Parse a YAML file using only safe constructors."""
    path = Path(path)
    if not path.exists():
        raise YAMLError(f"YAML file not found: {path}")
    try:
        return safe_load_yaml(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise YAMLError(f"Failed to read YAML file: {exc}") from exc
