# TASK-037 Dependency Confusion Mitigation — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Prevent dependency confusion attacks: internal package names should not be publishable, and installs should be pinned/verified.

---

## Current state (pre-work done by orchestrator)

Audited:

- `requirements.txt` — public PyPI packages only, no internal packages.
- `frontend/package.json` — public npm packages only.
- No `pyproject.toml` or `setup.py` exists yet; project is not a publishable Python package.
- No private package index or internal namespace is configured.

**Gaps identified:**

1. **No namespace reservation.** If the project later adds an internal package name like `taxflow-backend`, it could be squatted on PyPI/npm.
2. **No hash pinning.** `requirements.txt` uses version ranges (`>=`) rather than exact hashes or locked files.
3. **No CI step to verify package provenance.** No `--require-hashes` or `pip-audit` + hash verification.
4. **No documented policy.** Future contributors could add an internal package without a reserved namespace.

---

## Jane's tasks

### 1. Create `pyproject.toml` with project metadata and namespace guard

Add a non-publishable project metadata file at the repo root:

```toml
[project]
name = "taxflow-pro-private"  # non-squattable; not meant for PyPI
version = "3.9.2"
description = "Local-first tax and accounting pipeline (private)"
requires-python = ">=3.10"
dependencies = [
    # Keep empty; runtime deps remain in requirements.txt for now
]

[project.optional-dependencies]
dev = [
    # Keep empty or mirror requirements-dev.txt
]

[tool.setuptools]
py-modules = []
```

This claims the directory as an internal/private project and avoids accidental `pip install taxflow` naming.

### 2. Generate a lockfile with hashes

Use `pip-tools` if available, or generate a `requirements-lock.txt` with hashes:

```bash
python -m pip install pip-tools
pip-compile --generate-hashes --output-file requirements-lock.txt requirements.txt
```

If `pip-tools` is not available in the environment, create `requirements-lock.txt` manually by running:

```bash
python -m pip install --dry-run -r requirements.txt --report requirements-install-report.json
```

Then extract pinned versions + hashes from the report. At minimum, produce a `requirements-lock.txt` with exact pinned versions and `--hash=sha256:` lines.

Add a CI/pre-commit step that fails if `requirements-lock.txt` is out of sync with `requirements.txt`.

### 3. Reserve internal namespace in documentation

Add to `README.md` or `BUILDER_MANUAL.md`:

```markdown
## Internal Package Namespace

Any future internal Python packages or npm scopes must use one of these reserved prefixes:

- Python: `taxflow_private_*` or namespace under `backend/` only (not published)
- npm: `@taxflow/` private scope only

Do not create top-level PyPI/npm package names like `taxflow-core`, `taxflow-backend`, or `taxflow-common` without first confirming they cannot be squatted.
```

### 4. Add dependency-confusion test

Create `backend/tests/test_dependency_confusion.py`:

```python
def test_no_internal_package_names_on_public_indexes():
    """Internal package names must not look publishable."""
    from pathlib import Path
    pyproject = Path("pyproject.toml")
    assert pyproject.exists()
    text = pyproject.read_text()
    assert "name = \"taxflow-pro-private\"" in text or "taxflow_private" in text


def test_requirements_are_pinned_in_lockfile():
    """Lockfile exists and pins top-level requirements."""
    from pathlib import Path
    lock = Path("requirements-lock.txt")
    req = Path("requirements.txt")
    assert lock.exists()
    lock_text = lock.read_text()
    for line in req.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("=")[0].split(">")[0].split("<")[0].strip().lower()
        assert pkg in lock_text.lower(), f"{pkg} not pinned in requirements-lock.txt"
```

### 5. Add pre-commit / CI gate

If a pre-commit config exists (`.pre-commit-config.yaml`), add a hook:

```yaml
- repo: local
  hooks:
    - id: check-requirements-lock
      name: Check requirements-lock.txt is present
      entry: bash -c 'test -f requirements-lock.txt'
      language: system
      pass_filenames: false
      always_run: true
```

If no pre-commit config exists, add a note to `CHANGES.md` that CI should run the lockfile check.

### 6. Update `CHANGES.md`

Add a section for TASK-037 documenting:
- Files added: `pyproject.toml`, `requirements-lock.txt`, `backend/tests/test_dependency_confusion.py`.
- Files changed: `README.md` or `BUILDER_MANUAL.md`, `.pre-commit-config.yaml` (if exists).
- Behavior: internal namespace reservation, pinned lockfile, CI gate.

### 7. Run tests and report

```bash
python -m pytest backend/tests/test_dependency_confusion.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

Report pass/fail counts.

---

## Implementation notes

### pip-tools availability

If `pip-compile` is not installed, the fallback is to generate `requirements-lock.txt` by hand from the current environment:

```bash
python -m pip list --format=freeze > requirements-lock.txt
```

This is less secure than hashes but still pins versions. Prefer `pip-compile --generate-hashes` if possible.

### npm lockfile

`frontend/package-lock.json` already exists. Document that npm install must use `npm ci` in CI to respect the lockfile.

---

## Constraints

- Do not publish anything to PyPI/npm.
- Do not change runtime package versions in `requirements.txt` unless security-audit findings require it.
- Do not restart gateway or modify OpenClaw config.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- `pyproject.toml` with non-publishable name.
- `requirements-lock.txt` with pinned versions.
- `backend/tests/test_dependency_confusion.py`.
- Updated `README.md` / `BUILDER_MANUAL.md`.
- Optional pre-commit hook.
- Updated `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
