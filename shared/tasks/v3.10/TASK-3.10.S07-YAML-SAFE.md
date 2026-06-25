# TASK-3.10.S07 — YAML Safe Loading

**Owner:** TBD  
**Goal:** Ensure all YAML parsing uses `safe_load` to prevent arbitrary object deserialization.

## Files

- Any YAML loader (e.g., `categories.yaml`, parser templates)
- `backend/tests/test_yaml_safe_load.py`

## Requirements

1. Replace `yaml.load` with `yaml.safe_load` everywhere.
2. Add linting rule to block unsafe `yaml.load`.

## Tests

- Unsafe YAML payload rejected.
- Normal category YAML loads correctly.

## Report

Files changed, lint rule added, test results.
