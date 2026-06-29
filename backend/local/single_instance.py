"""Single-instance enforcement for TaxFlow Pro.

Ensures only one instance of the local server is running on a given host/port.
Uses a PID file in LOCAL_ROOT for fast detection, with socket probing as
fallback.
"""
from __future__ import annotations

import os
import platform
import socket
import sys
import time
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
LOCK_FILENAME = "taxflow.lock"
STALE_TIMEOUT_SECONDS = 10


def _lock_path(local_root: Path) -> Path:
    """Return the path to the PID lock file in LOCAL_ROOT."""
    return local_root / LOCK_FILENAME


def write_lock(local_root: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Path:
    """Write a PID lock file into LOCAL_ROOT."""
    path = _lock_path(local_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"{os.getpid()}\n{host}\n{port}\n"
    path.write_text(content, encoding="utf-8")
    return path


def read_lock(local_root: Path) -> dict | None:
    """Read the PID lock file. Returns dict with pid/host/port or None."""
    path = _lock_path(local_root)
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        return {
            "pid": int(lines[0]),
            "host": lines[1] if len(lines) > 1 else DEFAULT_HOST,
            "port": int(lines[2]) if len(lines) > 2 else DEFAULT_PORT,
        }
    except (ValueError, IndexError, OSError):
        return None


def remove_lock(local_root: Path) -> None:
    """Remove the lock file if it exists."""
    path = _lock_path(local_root)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
    except OSError:
        return False
    return True


def is_port_responsive(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is accepting connections and responds on /api/health."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def is_port_bound(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is already bound by any process."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.bind((host, port))
        return False
    except OSError:
        return True


def wait_for_process_exit(pid: int, timeout: float = STALE_TIMEOUT_SECONDS) -> bool:
    """Wait for a process to exit. Returns True if it exited, False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_process_alive(pid):
            return True
        time.sleep(0.5)
    return False


def bring_to_foreground(pid: int) -> None:
    """Attempt to bring the existing instance's window to foreground.

    Platform-specific:
      - Windows: uses ctypes to call SetForegroundWindow
      - macOS: uses AppleScript
      - Linux: tries wmctrl (best-effort)
    """
    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            # ASFW_ANY = -1 (allow any process to set foreground)
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
            # Find window by PID is non-trivial; instead we just try to
            # find any TaxFlow window by title.
            hwnd = ctypes.windll.user32.FindWindowW(None, "TaxFlow Pro")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    elif system == "Darwin":
        try:
            import subprocess
            subprocess.run(
                ["osascript", "-e",
                 'tell application "TaxFlow Pro" to activate'],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass

    elif system == "Linux":
        try:
            import subprocess
            subprocess.run(
                ["wmctrl", "-a", "TaxFlow Pro"],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass


def check_single_instance(
    local_root: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Check if another TaxFlow instance is running.

    Returns a dict with:
      - "action": "proceed" | "exit" | "replace"
      - "pid": PID of existing process (if any)
      - "reason": human-readable explanation
    """
    lock = read_lock(local_root)

    if lock is None:
        # No lock file — check if port is bound by something else
        if is_port_bound(host, port):
            return {
                "action": "exit",
                "pid": None,
                "reason": f"Port {host}:{port} is already in use by another process",
            }
        return {"action": "proceed", "pid": None, "reason": "No existing instance detected"}

    pid = lock["pid"]
    lock_host = lock.get("host", host)
    lock_port = lock.get("port", port)

    if not is_process_alive(pid):
        # Stale lock — process died without cleaning up
        remove_lock(local_root)
        return {"action": "replace", "pid": pid, "reason": f"Stale lock for PID {pid} — replacing"}

    if is_port_responsive(lock_host, lock_port):
        # Existing instance is alive and responding
        bring_to_foreground(pid)
        return {
            "action": "exit",
            "pid": pid,
            "reason": f"Existing instance running (PID {pid}) — brought to foreground",
        }

    # Process is alive but port is not responsive — might be starting up or stuck
    if wait_for_process_exit(pid, timeout=STALE_TIMEOUT_SECONDS):
        remove_lock(local_root)
        return {"action": "replace", "pid": pid, "reason": f"Process {pid} exited during wait — replacing"}

    # Process is stuck — try to kill and replace
    try:
        os.kill(pid, 9 if platform.system() != "Windows" else 9)
        time.sleep(1)
    except OSError:
        pass
    remove_lock(local_root)
    return {"action": "replace", "pid": pid, "reason": f"Process {pid} unresponsive — killed and replacing"}


def acquire_or_exit(
    local_root: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> bool:
    """Check for existing instance. If running, exit. If stale, replace.

    Returns True if this instance should proceed, False if it should exit.
    """
    result = check_single_instance(local_root, host, port)

    if result["action"] == "exit":
        print(f"[single-instance] {result['reason']}", file=sys.stderr)
        return False

    if result["action"] == "replace":
        print(f"[single-instance] {result['reason']}", file=sys.stderr)

    # Write our lock file
    write_lock(local_root, host, port)
    return True


def cleanup_on_exit(local_root: Path) -> None:
    """Remove the lock file on clean exit."""
    remove_lock(local_root)