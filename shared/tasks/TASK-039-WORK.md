# TASK-039 YAML Safe Loading — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Enforce `yaml.safe_load` / `CSafeLoader` everywhere YAML is parsed, add CI lint, and prevent unsafe object deserialization.

---

## Current state (pre-work done by orchestrator)

Scanned all Python and YAML files for YAML loading:

- `phase3_pipeline/categorizer.py:24` — `yaml.safe_load(f)` ✅
- `phase3_pipeline/category_loader.py:31` — `yaml.safe_load(f)` ✅
- `phase3_pipeline/profile_manager.py:32` — `yaml.safe_load(f)` ✅

No unsafe `yaml.load(...)` calls found. However, there is no centralized helper, no `CSafeLoader` optimization, and no CI lint to prevent future regressions.

**Gaps identified:**

1. No centralized `safe_load_yaml(path)` helper.
2. No `CSafeLoader` fallback for performance.
3. No lint/test that bans `yaml.load(...)` / `yaml.unsafe_load(...)`.
4. YAML files loaded from user upload paths (e.g., `categories.yaml`, profiles) could theoretically be attacker-controlled if a user points the app at a malicious file.

---

## Jane's tasks

### 1. Create `backend/local/yaml_safe.py`

Centralized safe YAML loader with CSafeLoader when available:

```python
"""Centralized safe YAML loading helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

import yaml


class YAMLError(Exception):
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
```

### 2. Replace existing `yaml.safe_load` calls

Update:

- `phase3_pipeline/categorizer.py`
- `phase3_pipeline/category_loader.py`
- `phase3_pipeline/profile_manager.py`

Replace direct `yaml.safe_load(f)` with `safe_load_yaml_file(self.rules_file)` (or `safe_load_yaml` if reading from text).

### 3. Add regression test

Create `backend/tests/test_yaml_safety.py`:

```python
import pytest
from pathlib import Path
from backend.local.yaml_safe import safe_load_yaml, safe_load_yaml_file, YAMLError


def test_safe_load_parses_simple_mapping():
    data = safe_load_yaml("foo: bar\nlist:\n  - 1\n  - 2")
    assert data == {"foo": "bar", "list": [1, 2]}


def test_safe_load_rejects_python_object(tmp_path):
    malicious = "!!python/object:__main__.Exploit\nfoo: bar"
    data = safe_load_yaml(malicious)
    assert data is None or "python/object" not in str(data)


def test_safe_load_yaml_file_missing():
    with pytest.raises(YAMLError):
        safe_load_yaml_file(tmp_path / "missing.yaml")


def test_no_unsafe_yaml_load_in_project():
    import ast
    root = Path(".")
    bad = []
    for path in list(root.rglob("*.py")):
        if "node_modules" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "load":
                    if isinstance(func.value, ast.Name) and func.value.id == "yaml":
                        if not any(k.arg == "Loader" for k in node.keywords):
                            bad.append(str(path))
    assert not bad, f"Unsafe yaml.load found in: {bad}"
```

### 4. Add pre-commit / CI lint

If `.pre-commit-config.yaml` exists, add a hook. Otherwise document the check in `CHANGES.md`.

### 5. Update `CHANGES.md`

Add section for TASK-039.

### 6. Run tests and report

```bash
python -m pytest backend/tests/test_yaml_safety.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

---

## Constraints

- Do not change YAML data semantics.
- Do not use `yaml.load(...)` with unsafe loaders.
- Do not restart gateway or modify OpenClaw config.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- New `backend/local/yaml_safe.py`.
- Updated `phase3_pipeline/*` loaders.
- New `backend/tests/test_yaml_safety.py`.
- Optional pre-commit hook.
- Updated `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
