"""Subprocess sandbox for isolated PDF parsing.

TaxFlow Pro v3.9.2 runs every PDF parser in a fresh Python process with
configurable CPU and memory limits. A malicious or malformed PDF cannot hang,
crash, or exhaust the main FastAPI worker.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Callable


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_MEMORY_MB = 512


class SandboxError(Exception):
    """Raised when the sandbox subprocess fails or the parser crashes."""


class SandboxTimeout(SandboxError):
    """Raised when the sandbox subprocess exceeds its CPU time budget."""


def _callable_to_path(target_callable: Callable[..., Any] | str) -> str:
    if isinstance(target_callable, str):
        return target_callable
    if not callable(target_callable):
        raise SandboxError(
            "target_callable must be a callable or a 'module.submodule:attr' string"
        )
    module = getattr(target_callable, "__module__", None)
    qualname = getattr(target_callable, "__qualname__", None)
    if not module or not qualname:
        raise SandboxError("Cannot serialize target callable to module path")
    return f"{module}:{qualname}"


def _sanitize_stderr(stderr: bytes) -> str:
    text = stderr.decode("utf-8", errors="replace").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    return " | ".join(lines[-5:])


def _make_memory_checker(process: subprocess.Popen[bytes], max_bytes: int) -> Callable[[], bool]:
    """Return a function that returns True if the child exceeds max_bytes RSS."""
    if os.name == "nt":
        return _make_windows_memory_checker(process, max_bytes)
    return _make_unix_memory_checker(process, max_bytes)


def _make_windows_memory_checker(process: subprocess.Popen[bytes], max_bytes: int) -> Callable[[], bool]:
    try:
        import ctypes
        # GetProcessMemoryInfo lives in psapi.dll on older Windows, kernel32 on modern builds.
        try:
            psapi = ctypes.windll.psapi
            get_process_memory_info = psapi.GetProcessMemoryInfo
        except Exception:
            get_process_memory_info = ctypes.windll.kernel32.GetProcessMemoryInfo

        get_process_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        get_process_memory_info.restype = ctypes.c_int

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        h_process = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, process.pid
        )
        if not h_process:
            return lambda: False

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        def check() -> bool:
            try:
                pmc = PROCESS_MEMORY_COUNTERS()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                if not get_process_memory_info(h_process, ctypes.byref(pmc), pmc.cb):
                    return False
                return bool(pmc.WorkingSetSize > max_bytes)
            except Exception:
                return False

        return check
    except Exception:
        return lambda: False


def _make_unix_memory_checker(process: subprocess.Popen[bytes], max_bytes: int) -> Callable[[], bool]:
    def check() -> bool:
        try:
            with open(f"/proc/{process.pid}/statm") as f:
                fields = f.read().split()
            rss_pages = int(fields[1])
            page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
            return bool(rss_pages * page_size > max_bytes)
        except Exception:
            return False

    return check


def run_in_sandbox(
    target_callable: Callable[..., Any] | str,
    *args: Any,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
) -> Any:
    """Run a callable in a restricted subprocess and return its result.

    ``target_callable`` may be a top-level function, a class method, or a string
    of the form ``module.submodule:attr[.nested_attr]``. Only JSON-serializable
    positional arguments are forwarded.

    The child is monitored from the parent: if it runs longer than the timeout it
    is killed, and if its resident set exceeds ``max_memory_mb`` it is killed.
    On Linux/macOS the child also applies ``RLIMIT_AS`` before importing parser
    libraries for defense in depth.

    Raises:
        SandboxTimeout: if the child process does not finish within the budget.
        SandboxError: if the child exits non-zero, exceeds memory, returns
            invalid JSON, or the target raises an exception.

    Returns:
        The JSON-deserialized return value of the target callable.
    """
    target_path = _callable_to_path(target_callable)

    payload = {
        "target": target_path,
        "args": list(args),
        "max_memory_mb": int(max_memory_mb),
    }

    env = os.environ.copy()
    cwd = os.getcwd()
    env.setdefault("PYTHONPATH", cwd)

    cmd = [sys.executable, "-m", "backend.parsers.sandbox_entry"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
    )

    # Send payload and close stdin so the child can read to EOF.
    try:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload).encode("utf-8"))
        proc.stdin.close()
    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        raise SandboxError(f"Failed to send payload to sandbox: {exc}") from exc

    max_bytes = int(max_memory_mb) * 1024 * 1024
    mem_check = _make_memory_checker(proc, max_bytes)

    killed_for_memory = False
    deadline = time.monotonic() + timeout_seconds
    poll_interval = 0.05

    try:
        while True:
            rc = proc.poll()
            if rc is not None:
                break

            if time.monotonic() > deadline:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
                raise SandboxTimeout(
                    f"PDF parser exceeded the {timeout_seconds}s sandbox timeout"
                )

            if not killed_for_memory and mem_check():
                proc.kill()
                killed_for_memory = True

            time.sleep(poll_interval)

        stdout, stderr = proc.communicate(timeout=5)
    except SandboxTimeout:
        raise
    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        raise SandboxError(f"Sandbox monitoring failed: {exc}") from exc

    if killed_for_memory or rc in (-9, 9):
        raise SandboxError("PDF parser exceeded the sandbox memory limit")

    if rc != 0:
        raise SandboxError(
            f"Sandbox process exited with code {rc}: "
            f"{_sanitize_stderr(stderr) or 'no stderr'}"
        )

    try:
        output_text = stdout.decode("utf-8", errors="replace")
        output = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise SandboxError(
            f"Sandbox returned invalid JSON: {exc}"
        ) from exc

    if isinstance(output, dict) and "__sandbox_error__" in output:
        detail = output["__sandbox_error__"]
        if output.get("__sandbox_timeout__"):
            raise SandboxTimeout(detail)
        raise SandboxError(detail)

    return output
