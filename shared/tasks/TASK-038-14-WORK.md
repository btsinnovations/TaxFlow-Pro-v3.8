# TASK-038.14 Simplify Single-User Default — Work Assignment

**Owner:** Jane  
**Approver:** btsinnovations (delegated by Josh)  
**Goal:** Add a `TAXFLOW_SINGLE_USER` flag so single-user mode never requires `X-Tenant-ID`, while preserving multi-entity mode behind an explicit opt-in.

---

## Current state (pre-work done by orchestrator)

Already implemented:
- `backend/rls.py` has `resolve_user_tenant_id(user)` and `get_current_tenant(request, current_user, x_tenant_id)` helpers.
- Most routers already derive the tenant from the user's primary client when no header is provided (e.g., `accounts.py`, `clients.py`, `depreciation.py`, `flags.py`, `gl.py`, `rules.py`, `tax.py`, `transactions.py`, `upload.py`).

**Remaining gap:** Several code paths still raise `HTTPException(400, "X-Tenant-ID header required")` when no header is sent in PostgreSQL mode, even though `resolve_user_tenant_id` is available. These need to honor a new `TAXFLOW_SINGLE_USER` flag.

---

## Jane's tasks

### 1. Add single-user flag to `backend/local/settings.py`

```python
TAXFLOW_SINGLE_USER = os.environ.get("TAXFLOW_SINGLE_USER", "true").lower() in ("1", "true", "yes")


def is_single_user() -> bool:
    return TAXFLOW_SINGLE_USER
```

### 2. Update `backend/rls.py` helpers

Modify `get_current_tenant` so that in single-user mode it always returns `resolve_user_tenant_id(current_user)` regardless of whether a header is present.

### 3. Update remaining strict header checks

Find all `HTTPException(400, "X-Tenant-ID header required")` and make them conditional on `not is_single_user()`. Files likely needing updates:
- `backend/routers/accounts.py`
- `backend/routers/clients.py`
- `backend/routers/depreciation.py`
- `backend/routers/flags.py`
- `backend/routers/gl.py`
- `backend/routers/rules.py`
- `backend/routers/tax.py`
- `backend/routers/transactions.py`
- `backend/routers/upload.py`

### 4. Add/update tests

Create `backend/tests/test_single_user_mode.py`:
- `test_single_user_mode_default_true` — `is_single_user()` is True by default.
- `test_no_tenant_header_required_for_single_user_sqlite` — request without `X-Tenant-ID` succeeds.
- `test_x_tenant_id_header_ignored_in_single_user_sqlite` — arbitrary header value is ignored.
- `test_multi_entity_mode_requires_tenant_header_on_postgres` — monkeypatch `TAXFLOW_SINGLE_USER=false` and `is_postgres()` returns True; request without header returns 400.

### 5. Update `docs/TODO_FIRST.md`

Mark Phase 3 Gap **3.11 Simplify single-user default** as ✅ complete.

### 6. Update `CHANGES.md`

Add Section 39 — Simplify Single-User Default (TASK-038.14 / 3.11).

### 7. Run tests and report

```bash
python -m pytest backend/tests/test_single_user_mode.py -q
python -m pytest backend/tests -q
python -m pytest tests -q
```

---

## Constraints

- Do not break multi-entity tests.
- Default to single-user-friendly behavior.
- No gateway restart / OpenClaw config changes.
- Escalate blockers via `sessions_send` to James.

---

## Expected output

- Updated `backend/local/settings.py`.
- Updated `backend/rls.py`.
- Updated strict header checks in routers.
- New `backend/tests/test_single_user_mode.py`.
- Updated `docs/TODO_FIRST.md` and `CHANGES.md`.
- Test report with 0 failures.

Start when ready. Report progress via sessions_send only.
