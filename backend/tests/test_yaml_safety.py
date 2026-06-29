"""Tests for safe YAML loading (TASK-039)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.local.yaml_safe import safe_load_yaml, safe_load_yaml_file, YAMLError


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_safe_load_yaml_parses_simple_mapping() -> None:
    data = safe_load_yaml("foo: bar\nlist:\n  - 1\n  - 2")
    assert data == {"foo": "bar", "list": [1, 2]}


def test_safe_load_yaml_rejects_python_object() -> None:
    malicious = "!!python/object:__main__.Exploit\nfoo: bar"
    with pytest.raises(YAMLError):
        safe_load_yaml(malicious)


def test_safe_load_yaml_file_missing(tmp_path: Path) -> None:
    with pytest.raises(YAMLError):
        safe_load_yaml_file(tmp_path / "missing.yaml")


def test_no_unsafe_yaml_load_in_project() -> None:
    """AST scan: no yaml.load() call lacks an explicit Loader."""
    bad: list[str] = []
    for path in PROJECT_ROOT.rglob("*.py"):
        if any(skip in path.parts for skip in ("node_modules", "dist", "build")):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load":
                if isinstance(func.value, ast.Name) and func.value.id == "yaml":
                    if not any(k.arg == "Loader" for k in node.keywords):
                        bad.append(str(path))
            # Also catch yaml.unsafe_load / yaml.full_load explicitly
            if isinstance(func, ast.Attribute) and func.attr in ("unsafe_load", "full_load"):
                if isinstance(func.value, ast.Name) and func.value.id == "yaml":
                    bad.append(str(path))
    assert not bad, f"Unsafe yaml.load calls found in: {bad}"


def test_phase3_pipeline_uses_yaml_safe_loader() -> None:
    """Ensure pipeline modules import safe_load_yaml_file instead of yaml.safe_load."""
    targets = [
        PROJECT_ROOT / "pipeline" / "categorizer.py",
        PROJECT_ROOT / "pipeline" / "category_loader.py",
        PROJECT_ROOT / "pipeline" / "profile_manager.py",
    ]
    for path in targets:
        source = path.read_text(encoding="utf-8")
        assert "from backend.local.yaml_safe import safe_load_yaml_file" in source, f"{path} does not import safe_load_yaml_file"
        assert "yaml.safe_load" not in source, f"{path} still uses yaml.safe_load"
        assert "import yaml" not in source, f"{path} still imports yaml"
