# TASK-036 Sensitive Data in Process Arguments — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Remove sensitive values (database passwords, secrets, tokens) from process command-line arguments and environment exposure.

---

## Current state (pre-work done by orchestrator)

Audited:

- `start.sh` — passes `backend.api:app` to uvicorn but does not pass `DATABASE_URL` on the command line. The script sources a virtual env and runs uvicorn. No direct password leak in argv.
- `alembic.ini` — contains `sqlalchemy.url = sqlite:///./taxflow.db` (default template, no password). The app overrides this at runtime.
- `backend/database.py` — reads `DATABASE_URL` from environment. If the URL contains a password, it is visible in the process environment but not argv.
- `backend/local/settings.py` — reads `TAXFLOW_DB_PASSWORD`, `TAXFLOW_DB_KEYFILE`, `TAXFLOW_DB_KEYRING_TOKEN` from environment.

**Gaps identified:**

1. **Environment variables are still visible to any process on the machine.** On shared systems, `ps e -p <pid>` or `/proc/<pid>/environ` exposes these values.
2. **No canonical secrets-file path.** There is no documented `TAXFLOW_SECRETS_FILE` or `.secrets` convention.
3. **Scripts may echo or log the URL.** Need to verify no script logs `DATABASE_URL` or `TAXFLOW_DB_PASSWORD`.
4. **`start.sh` has `set -e` but does not sanitize args.** If a user runs `DATABASE_URL=postgresql://user:pass@host/db ./start.sh`, the password is in env, not argv — acceptable, but we should document the secrets-file alternative.

---

## Jane's tasks

### 1. Add secrets-file support to `backend/local/settings.py`

Add:

```python
TAXFLOW_SECRETS_FILE = os.environ.get("TAXFLOW_SECRETS_FILE")

def _load_secrets_file() -> dict:
    """Load key=value pairs from a secrets file outside version control."""
    path_str = TAXFLOW_SECRETS_FILE
    if not path_str:
        return {}
    path = Path(path_str).expanduser()
    if not path.exists():
        return {}
    secrets = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        secrets[key.strip()] = value.strip()
    return secrets

_SECRETS = _load_secrets_file()
```

Then update sensitive env reads to prefer the secrets file while keeping env fallback:

```python
SQLCIPHER_PASSWORD = _SECRETS.get("TAXFLOW_DB_PASSWORD", os.environ.get("TAXFLOW_DB_PASSWORD", ""))
SQLCIPHER_KEYFILE = _SECRETS.get("TAXFLOW_DB_KEYFILE", os.environ.get("TAXFLOW_DB_KEYFILE", None))
SQLCIPHER_KEYRING_TOKEN = _SECRETS.get("TAXFLOW_DB_KEYRING_TOKEN", os.environ.get("TAXFLOW_DB_KEYRING_TOKEN", None))
```

Do the same for `DATABASE_URL` in `backend/database.py`:

```python
from backend.local.settings import _SECRETS
DATABASE_URL = _SECRETS.get("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///./taxflow.db"))
```

### 2. Add helper to redact URLs for logging

Add to `backend/local/settings.py`:

```python
import re

def redact_url(url: str) -> str:
    """Remove password from a URL before logging."""
    return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", url)
```

Use `redact_url(DATABASE_URL)` anywhere the URL is logged. Search for logging of `DATABASE_URL`.

### 3. Audit and remove secret logging

Search `backend/`, `scripts/`, `start.sh`, and any `.py` files for:
- `DATABASE_URL` in print/logging statements.
- `TAXFLOW_DB_PASSWORD` in print/logging statements.
- `LOCAL_SECRET_FILE` content being printed.

Replace with redacted forms or remove.

### 4. Add `.env.example` guidance

Add:

```bash
# Option A: environment variables (convenient, visible in /proc on Linux)
# DATABASE_URL=sqlite:///./taxflow.db
# TAXFLOW_DB_PASSWORD=...

# Option B: secrets file (preferred for passwords; file should be 0600 / user-only)
# TAXFLOW_SECRETS_FILE=/secure/path/to/taxflow.secrets
```

### 5. Add tests

Create `backend/tests/test_secret_handling.py`:

- `test_secrets_file_overrides_env`
  - Create a temp secrets file with `DATABASE_URL=...` and `TAXFLOW_DB_PASSWORD=...`.
  - Monkeypatch `TAXFLOW_SECRETS_FILE` to that path.
  - Re-import or call a helper and assert values come from file.
- `test_redact_url_obscures_password`
  - Assert `redact_url("postgresql://user:secret@host/db")` returns `postgresql://user:***@host/db`.
- `test_database_url_not_logged_with_password`
  - Capture logs during engine creation and assert the password does not appear.

### 6. Update `CHANGES.md`

Add a section for TASK-036 documenting:
- Files changed: `backend/local/settings.py`, `backend/database.py`, `.env.example`.
- Files added: `backend/tests/test_secret_handling.py`.
- Behavior: secrets-file support, env fallback, URL redaction for logs.

### 7. Run tests and report

```bash
python -m pytest backend/tests/test_secret_handling.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

Report pass/fail counts.

---

## Constraints

- Keep backward compatibility: env vars continue to work.
- Do not break existing tests that rely on env-based `DATABASE_URL`.
- Do not restart gateway or modify OpenClaw config.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- Updated `backend/local/settings.py` and `backend/database.py`.
- New `backend/tests/test_secret_handling.py`.
- Updated `.env.example`.
- Updated `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
