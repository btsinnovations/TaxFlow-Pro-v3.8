# TASK-038.8 Dependency Audit — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Context:** James has updated `docs/DEPENDENCY_AUDIT.md` with the initial findings. This task is to finalize the audit, make any required code changes, and update documentation/tests.

---

## Pre-work already completed by orchestrator

1. ✅ Updated `docs/DEPENDENCY_AUDIT.md` with:
   - Executive summary
   - Backend production dependency table
   - `requests` usage verification result
   - Frontend dependency table
   - Action items and sign-off
2. ✅ Verified no runtime backend import of `requests`, `urllib.request`, `http.client`, or `httpx`.
3. ✅ Confirmed only local/diagnostic socket usage exists (`backend/local/guards.py`, `backend/local/offline.py`, `backend/auth.py` hostname).
4. ✅ Created starter audit script: `scripts/dependency_audit.py` (optional; not required to run unless you want to regenerate).

---

## Jane's remaining tasks

### 1. Verify `requests` can be removed
- Inspect `requirements.txt`.
- Remove the line `requests>=2.31.0`.
- Run `python -m pytest backend/tests -q --tb=short`.
- If tests pass, commit the removal. If any test fails, report which one and do not proceed.

### 2. Add runtime guard test
Create or extend `backend/tests/test_local_first.py` with a test that asserts:
- No backend runtime module imports `requests`, `urllib.request`, `http.client`, or `httpx`.
- `FEATURE_FLAGS` defaults keep cloud features disabled.

Sample assertion pattern:
```python
import ast
from pathlib import Path

RUNTIME_DIRS = [Path("backend"), Path("phase3_pipeline")]
FORBIDDEN_IMPORTS = {"requests", "urllib.request", "http.client", "httpx", "aiohttp"}

def test_no_forbidden_network_imports():
    imports = set()
    for d in RUNTIME_DIRS:
        for p in d.rglob("*.py"):
            if "tests" in p.parts:
                continue
            tree = ast.parse(p.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
    forbidden = imports & FORBIDDEN_IMPORTS
    assert not forbidden, f"Forbidden network imports found: {forbidden}"
```

### 3. Document frontend Google Fonts decision
- Open `docs/OFFLINE_BEHAVIOR.md` (create if missing).
- Add section: "External assets — Google Fonts are loaded from `fonts.googleapis.com` for the web/dev build. No user data flows through this request. For a fully offline installer, vendor fonts into `frontend/public/fonts/` and update `frontend/index.html`."

### 4. Update `docs/TODO_FIRST.md`
- Find the Phase 3 / 3.1 Dependency Audit line.
- Mark as complete.

### 5. Update `CHANGES.md`
- Add entry under the current version for dependency audit completion.

### 6. Final verification
- Run full backend tests: `python -m pytest backend/tests -q --tb=short`
- Report pass/fail count.
- If 100% pass, mark TASK-038.8 complete in `shared/tasks/TASK-038-SUBTASKS.md` and hand back to orchestrator.

---

## Constraints

- Do NOT remove any dependency unless tests still pass after removal.
- Do NOT change `FEATURE_FLAGS` defaults or cloud gating policy; that was handled in TASK-038.6.
- Do NOT restart gateway or change OpenClaw config.
- Escalate blockers via `sessions_send` to James, not public Discord.

---

## Expected output

- Updated `requirements.txt` (with `requests` removed, if safe).
- Updated `backend/tests/test_local_first.py` (or new test file).
- Updated `docs/OFFLINE_BEHAVIOR.md`.
- Updated `docs/TODO_FIRST.md`.
- Updated `CHANGES.md`.
- Updated `shared/tasks/TASK-038-SUBTASKS.md`.
- Test report: `X passed, Y warnings, 0 failed`.

Start when ready. Report progress via sessions_send only.
