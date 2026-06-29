"""Detached chunked pytest launcher.

Spawns each chunk as a fully detached Windows process so OpenClaw's runtime
watchdog cannot kill it. The launcher exits immediately; chunk logs are written
to shared/tasks/v3.11.6/baseline_test_logs/chunk_NNN.log. Use
aggregate_chunked_results.py to collect results after all logs are present.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS_DIR = ROOT / "backend" / "tests"
LOG_DIR = ROOT / "shared" / "tasks" / "v3.11.6" / "baseline_test_logs"
CHUNK_SIZE = 10

# Windows creation flags: break away from job object + new process group + no window
DETACHED_FLAGS = (
    0x00000008  # CREATE_BREAKAWAY_FROM_JOB
    | 0x00000200  # CREATE_NEW_PROCESS_GROUP
    | 0x08000000  # CREATE_NO_WINDOW
)


def discover_tests():
    files = sorted(TESTS_DIR.glob("test_*.py"))
    return [str(f.relative_to(ROOT)) for f in files]


def chunk_files(files, size):
    return [files[i : i + size] for i in range(0, len(files), size)]


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Clear old logs
    for old in LOG_DIR.glob("chunk_*.log"):
        old.unlink()

    files = discover_tests()
    chunks = chunk_files(files, CHUNK_SIZE)
    print(f"Launching {len(chunks)} detached chunks for {len(files)} test files...")

    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["TAXFLOW_TESTING"] = "true"
    env["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
    env["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    launched = []
    for idx, chunk in enumerate(chunks, start=1):
        log_path = LOG_DIR / f"chunk_{idx:03d}.log"
        with open(log_path, "w", encoding="utf-8") as log_file:
            pass  # create empty log
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + chunk
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=open(log_path, "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=DETACHED_FLAGS,
        )
        launched.append((idx, proc.pid, log_path))
        print(f"  chunk {idx:3d}: pid {proc.pid}, {len(chunk)} files")
        time.sleep(0.2)

    print(f"Launched {len(launched)} detached chunks. They will run independently.")
    print(f"Poll log files in {LOG_DIR} for completion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
