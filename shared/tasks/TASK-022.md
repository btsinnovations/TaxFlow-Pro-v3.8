# TASK-022: Parser Subprocess Sandbox

## Metadata
- **Project:** TaxFlow Pro v3.9.2
- **Assigned by:** James Clawd (orchestrator)
- **Deadline:** 2026-06-21 23:59 America/New_York
- **Status:** COMPLETE
- **Completed:** 2026-06-21

## Objective
Isolate PDF parsing from the main TaxFlow Pro FastAPI process. Run every parser in a restricted subprocess with CPU and memory limits so a malicious or malformed PDF cannot hang, crash, or compromise the backend.

## Deliverables

### 1. `backend/parsers/sandbox.py`
New module providing:
- `SandboxError` / `SandboxTimeout` exception types.
- `run_in_sandbox(target_callable, *args, timeout_seconds=30.0, max_memory_mb=512)`.
- Spawns a fresh Python subprocess running `python -m backend.parsers.sandbox_entry`.
- Sends a JSON payload to the child's stdin and reads a JSON result from stdout.
- Monitors elapsed time and child RSS memory; kills the child if either budget is exceeded.
- Converts exceptions and non-zero exits into structured `SandboxError`/`SandboxTimeout` without leaking tracebacks.

### 2. `backend/parsers/sandbox_entry.py`
Minimal `__main__`-guarded helper script:
- Reads JSON payload from stdin.
- Applies platform-specific resource limits *before* importing heavy parser libraries:
  - Linux/macOS: `resource.setrlimit(RLIMIT_AS)`.
  - Windows: working-set hint via `SetProcessWorkingSetSizeEx`.
- Resolves `module.submodule:attr[.nested]` target path with `importlib`.
- Calls the target and writes JSON output; structured errors use `{"__sandbox_error__": ...}`.

### 3. Refactored parser invocation
`backend/routers/upload.py` no longer calls `parse_statement_pdf()` directly in the FastAPI process. Instead it uses:

```python
result = run_in_sandbox(
    "backend.parsers.institution:parse_statement_pdf",
    str(file_path),
    {"force_ocr": force_ocr},
    timeout_seconds=30.0,
    max_memory_mb=512,
)
```

Sandbox timeout/error raise `HTTPException(status_code=422, detail="PDF could not be parsed safely")`.

### 4. `backend/tests/test_parser_sandbox.py`
New test suite covering:
- Valid TD Bank-style PDF parses successfully through the sandbox.
- Regression fixture produces the canonical result shape through the sandbox.
- Infinite-loop target is killed at timeout (`SandboxTimeout`).
- Memory-hog target is killed when RSS exceeds the budget (`SandboxError`).
- Exception-raising target returns `SandboxError` without a traceback in the message.

### 5. Updated `.env.example`
Added:
```
TAXFLOW_PARSER_TIMEOUT_SECONDS=30
TAXFLOW_PARSER_MAX_MEMORY_MB=512
```

### 6. Updated `README.md`
Added a **Parser Security** section documenting:
- Subprocess sandbox architecture.
- Default 30s / 512 MiB limits.
- Platform hard-limit mechanisms (RLIMIT_AS / job-object/working-set hint).
- Generic 422 error with no traceback leakage.

## Test Results
- `pytest backend/tests/test_parser_sandbox.py -v` → **5 passed, 0 failed**
- `pytest backend/tests/test_parser_regression.py backend/tests/test_ocr_parser.py backend/tests/test_parser_sandbox.py backend/tests/test_upload_security.py backend/tests/test_api.py -v` → **44 passed, 0 failed**
- Combined targeted run (parser_sandbox, parser_regression, ocr_parser, upload_security, test_api, backup_restore, audit_trail, keyring_secret, hybrid_auth) → **90 passed, 0 failed**

## Files Changed
- `backend/parsers/sandbox.py` (new)
- `backend/parsers/sandbox_entry.py` (new)
- `backend/routers/upload.py`
- `backend/tests/test_parser_sandbox.py` (new)
- `.env.example`
- `README.md`

## Notes
- No commit per project instructions; v3.9.2 changes remain batched for a single commit.
- No new runtime dependencies were required; all sandbox functionality uses the standard library plus existing parser dependencies.

## Verification Steps
```bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
python -m pytest backend/tests/test_parser_sandbox.py -v
python -m pytest backend/tests/test_parser_regression.py backend/tests/test_ocr_parser.py backend/tests/test_parser_sandbox.py backend/tests/test_upload_security.py backend/tests/test_api.py -v
```
