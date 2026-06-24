> **Note:** This task shares the number "038" with the Phase 3 Foundation sub-tasks (TASK-038.x) but is a separate v3.9.2 security task. To avoid confusion, refer to it as **TASK-038-Entropy-Audit** in status updates.

# TASK-038-Entropy-Audit Weak Entropy Audit — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Replace any remaining low-entropy or predictable random usage with `secrets` module calls; audit all token/key generation.

---

## Current state (pre-work done by orchestrator)

The project already uses `secrets` and `os.urandom` in security-sensitive paths, but a full audit has not been run. We need to verify that no code path relies on `random` or `numpy.random` for security purposes (tokens, keys, nonces, salts, passwords, session IDs, CSRF tokens).

---

## Jane's tasks

### 1. Run a full scan for insecure random usage

Search `backend/`, `phase3_pipeline/`, `scripts/`, `frontend/src/` for:

- `import random` or `from random import ...`
- `random.` function calls
- `numpy.random` for anything other than ML training/data augmentation
- `uuid.uuid1()` (MAC address leak risk)
- `uuid.uuid4()` is acceptable for non-security identifiers but not for secrets

Generate a report listing each hit with file, line, and context.

### 2. Categorize each hit

| Category | Action |
|---|---|
| Security-sensitive (tokens, keys, salts, nonces, passwords) | Replace with `secrets` |
| Deterministic/test-only (fuzz seeds, reproducible ML) | Keep, but add `# TEST-ONLY: not for security` comment |
| Non-security (UI jitter, sampling, simulation) | Keep, but add `# NON-SECURITY` comment |
| Unknown | Flag for review |

### 3. Replace security-sensitive random usage

Add a helper in `backend/local/security_random.py`:

```python
"""Cryptographically secure random helpers."""
import secrets
import string


def secure_token(nbytes: int = 32) -> str:
    """URL-safe random token as hex."""
    return secrets.token_hex(nbytes)


def secure_urlsafe_token(nbytes: int = 32) -> str:
    """URL-safe base64 random token."""
    return secrets.token_urlsafe(nbytes)


def secure_random_int(min_val: int, max_val: int) -> int:
    """secrets.randbelow wrapper for an inclusive range."""
    if min_val >= max_val:
        raise ValueError("min_val must be less than max_val")
    return min_val + secrets.randbelow(max_val - min_val + 1)


def secure_alphanumeric(length: int = 16) -> str:
    """Random alphanumeric string for non-secret identifiers."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
```

Replace usages such as:
- `random.choice(...)` for password generation → `secure_alphanumeric` or `secure_urlsafe_token`
- `random.randint(...)` for token/ID generation → `secure_random_int`
- `random.seed(...)` for security → delete

### 4. Audit token/key generation

Read these files and confirm they use `secrets` or `os.urandom`:

- `backend/auth.py` — local secret, session token, refresh token, JWT secret
- `backend/local/crypto.py` — salt, nonce, Argon2
- `backend/local/keyring_secret.py` — fallback secret generation
- `backend/routers/auth.py` — token creation
- `backend/rate_limit.py` — if it uses randomness, ensure it is not security-sensitive

If any of these use `random` or low-entropy UUIDs, replace them.

### 5. Add tests

Create `backend/tests/test_entropy_audit.py`:

```python
def test_no_random_import_in_security_modules():
    """Security-critical modules must not import the stdlib random module."""
    import ast
    from pathlib import Path
    security_modules = [
        Path("backend/auth.py"),
        Path("backend/local/crypto.py"),
        Path("backend/local/keyring_secret.py"),
        Path("backend/routers/auth.py"),
    ]
    for path in security_modules:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "random", f"{path} imports random"
            if isinstance(node, ast.ImportFrom):
                if node.module == "random":
                    raise AssertionError(f"{path} imports from random")


def test_secure_token_is_hex():
    from backend.local.security_random import secure_token
    token = secure_token()
    assert len(token) == 64
    assert int(token, 16) >= 0


def test_secure_random_int_range():
    from backend.local.security_random import secure_random_int
    for _ in range(100):
        v = secure_random_int(10, 20)
        assert 10 <= v <= 20
```

### 6. Update `CHANGES.md`

Add a section for TASK-038-Entropy-Audit documenting:
- Files added: `backend/local/security_random.py`, `backend/tests/test_entropy_audit.py`.
- Files changed: any modules where `random` was replaced.
- Behavior: security-sensitive randomness uses `secrets`; non-security usage is explicitly labeled.

### 7. Run tests and report

```bash
python -m pytest backend/tests/test_entropy_audit.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

Report pass/fail counts.

---

## Implementation notes

### ML training exceptions

`scikit-learn` and `numpy.random` used inside model training for train/test splits or data augmentation are acceptable, provided:
- They are not used for secrets.
- They are reproducible when a seed is explicitly set for tests.

Mark such usage with comments.

### UUIDs

- `uuid.uuid4()` is fine for non-secret record identifiers.
- Never use `uuid.uuid1()` (MAC leak).
- For bearer tokens, session IDs, and signing secrets, prefer `secrets.token_urlsafe`.

---

## Constraints

- Do not change ML training behavior unless required for security.
- Do not restart gateway or modify OpenClaw config.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- Audit report of `random`/`numpy.random`/`uuid.uuid1` hits with disposition.
- Updated security modules using `secrets`.
- New `backend/local/security_random.py`.
- New `backend/tests/test_entropy_audit.py`.
- Updated `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
