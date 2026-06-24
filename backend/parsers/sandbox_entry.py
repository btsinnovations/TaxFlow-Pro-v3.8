"""Subprocess entry point for the PDF parser sandbox.

This module is invoked by ``python -m backend.parsers.sandbox_entry``. It:

1. Reads a JSON payload from stdin describing the target callable and args.
2. Applies platform-specific resource limits *before* importing heavy parser libs.
3. Imports and calls the target.
4. Writes a JSON result (or a structured error) to stdout.

Keep imports minimal until after resource limits are applied.
"""
from __future__ import annotations

import importlib
import json
import os
import struct
import sys
import traceback
from typing import Any


# Same defaults as backend/parsers/pdf_guard.py; enforced inside the sandbox
# before any parser library is imported.
MAX_FILE_SIZE_BYTES = 32 * 1024 * 1024
MAX_PAGES = 100


def _apply_resource_limits(max_memory_mb: int) -> None:
    """Set hard memory limits in the child process before parsing begins."""
    if not max_memory_mb or max_memory_mb <= 0:
        return

    # Linux / macOS: virtual address-space cap.
    try:
        import resource

        limit_bytes = max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except Exception:
        pass

    # Windows: there is no reliable per-process hard memory cap that applies to
    # all allocations without admin rights. We leave enforcement to the parent's
    # RSS polling (see backend/parsers/sandbox.py), but we do try to configure a
    # small working-set hint so the parser cannot easily pin large amounts of
    # physical memory. Failure is non-fatal.
    try:
        _apply_windows_working_set_hint(max_memory_mb)
    except Exception:
        pass


def _apply_windows_working_set_hint(max_memory_mb: int) -> None:
    if os.name != "nt":
        return

    import ctypes

    kernel32 = ctypes.windll.kernel32
    pid = os.getpid()
    PROCESS_SET_QUOTA = 0x0100
    h_process = kernel32.OpenProcess(PROCESS_SET_QUOTA, False, pid)
    if not h_process:
        return

    max_bytes = max_memory_mb * 1024 * 1024
    min_bytes = min(4 * 1024 * 1024, max_bytes // 4)

    SetProcessWorkingSetSizeEx = kernel32.SetProcessWorkingSetSizeEx
    SetProcessWorkingSetSizeEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_uint32,
    ]
    SetProcessWorkingSetSizeEx.restype = ctypes.c_int

    # 0x01 = QUOTA_LIMITS_HARDWS_MIN_ENABLE, 0x02 = QUOTA_LIMITS_HARDWS_MAX_DISABLE
    # We use neither; this is a soft hint. The parent enforces the real cap.
    SetProcessWorkingSetSizeEx(h_process, min_bytes, max_bytes, 0)
    kernel32.CloseHandle(h_process)


# Kept for reference; JOB_OBJECT_LIMIT_JOB_MEMORY is documented but returns
# ERROR_INVALID_PARAMETER on many consumer Windows builds when used without
# additional undocumented fields.
def _apply_windows_memory_limit(max_memory_mb: int) -> None:
    if os.name != "nt":
        return

    import ctypes

    kernel32 = ctypes.windll.kernel32
    h_job = kernel32.CreateJobObjectW(None, None)
    if not h_job:
        return

    memory_bytes = max_memory_mb * 1024 * 1024

    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION layout on 64-bit Windows:
    #   JOBOBJECT_BASIC_LIMIT_INFORMATION (64 bytes)
    #   IO_COUNTERS (48 bytes)
    #   JobMemoryLimit (SIZE_T, 8 bytes)
    #   PeakProcessMemoryUsed (SIZE_T, 8 bytes)
    #   PeakJobMemoryUsed (SIZE_T, 8 bytes)
    buf_size = 64 + 48 + 8 + 8 + 8
    buf = ctypes.create_string_buffer(buf_size)

    # LimitFlags field is at offset 16 inside BasicLimitInformation.
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    struct.pack_into("<I", buf, 16, JOB_OBJECT_LIMIT_JOB_MEMORY)

    # JobMemoryLimit field is at offset 112.
    struct.pack_into("<Q", buf, 112, memory_bytes)

    # The job-object limit layout accepted by this Windows build is 144
    # bytes (136 bytes of extended limit info + 8 bytes of undocumented padding).
    buf_size = ctypes.sizeof(buf) + 8
    raw_buf = ctypes.create_string_buffer(buf_size)
    ctypes.memmove(ctypes.byref(raw_buf), ctypes.byref(buf), ctypes.sizeof(buf))

    JobObjectExtendedLimitInformation = 9
    if not kernel32.SetInformationJobObject(
        h_job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(raw_buf),
        buf_size,
    ):
        return

    # Assign the current process to the job. This may fail if the parent
    # already placed us in a job, but the timeout still protects the host.
    kernel32.AssignProcessToJobObject(h_job, kernel32.GetCurrentProcess())


def _resolve_target(target_path: str) -> Any:
    module_name, attr_path = target_path.rsplit(":", 1)
    module = importlib.import_module(module_name)
    obj = module
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def _write_json(obj: Any) -> None:
    sys.stdout.write(json.dumps(obj, default=str, ensure_ascii=False))
    sys.stdout.flush()


def _error_out(message: str, is_timeout: bool = False) -> None:
    err = {"__sandbox_error__": message}
    if is_timeout:
        err["__sandbox_timeout__"] = True
    _write_json(err)


def main() -> None:
    raw_payload = sys.stdin.read()
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        _error_out(f"Invalid sandbox payload JSON: {exc}")
        return

    if not isinstance(payload, dict):
        _error_out("Sandbox payload must be a JSON object")
        return

    target_path = payload.get("target")
    if not target_path or not isinstance(target_path, str):
        _error_out("Sandbox payload missing string 'target' field")
        return

    max_memory_mb = payload.get("max_memory_mb", 512)
    _apply_resource_limits(int(max_memory_mb))

    # If the first positional argument is a PDF path, run static guards before
    # importing heavy parser libraries. This protects against files that somehow
    # passed the parent-process validator.
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", {})
    if args and isinstance(args[0], str):
        pdf_path = args[0]
        try:
            from backend.parsers.pdf_guard import inspect_pdf_file, PDFGuardError

            result = inspect_pdf_file(
                pdf_path,
                max_size_bytes=MAX_FILE_SIZE_BYTES,
                max_pages=MAX_PAGES,
            )
            if not result.ok:
                raise PDFGuardError(result.reason or "PDF failed sandbox safety checks")
        except PDFGuardError as exc:
            _error_out(str(exc))
            return
        except Exception as exc:
            # Missing pdf_guard (should not happen) is not fatal; continue to
            # the parser library which may enforce its own limits.
            sys.stderr.write(f"sandbox guard warning: {exc}\n")

    try:
        target = _resolve_target(target_path)
        result = target(*args, **kwargs)
    except Exception as exc:
        # Structured error only; raw traceback stays server-side stderr.
        _error_out(str(exc))
        return

    try:
        _write_json(result)
    except Exception as exc:
        _error_out(f"Failed to serialize parser result: {exc}")


if __name__ == "__main__":
    main()
