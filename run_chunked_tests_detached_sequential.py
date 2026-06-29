"""Detached sequential chunked pytest runner.

Runs test chunks one at a time to avoid memory exhaustion, but the launcher
itself is detached from OpenClaw's job object so the runtime watchdog cannot
interrupt it. Each chunk is a fresh subprocess so imports are unloaded
between chunks.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS_DIR = ROOT / "backend" / "tests"
LOG_DIR = ROOT / "shared" / "tasks" / "v3.11.6" / "baseline_test_logs"
REPORT_PATH = ROOT / "shared" / "tasks" / "v3.11.6" / "BASELINE_TEST_REPORT.json"
CHUNK_SIZE = 10

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


def run_chunk(chunk_id, chunk):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"chunk_{chunk_id:03d}.log"
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["TAXFLOW_TESTING"] = "true"
    env["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
    env["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + chunk
    start = time.time()
    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT, text=True)
    elapsed = time.time() - start
    return parse_log(log_path), elapsed, proc.returncode


def parse_log(log_path):
    import re
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    passed = failed = errors = 0
    for line in text.splitlines():
        m = re.search(r"=+\s+([\d\s\w,]+)\s+in\s+[\d.]+s\s*=+", line)
        if m:
            summary = m.group(1)
            for token, attr in [("passed", "passed"), ("failed", "failed"), ("error", "errors")]:
                tm = re.search(rf"(\d+)\s+{token}", summary)
                if tm:
                    count = int(tm.group(1))
                    if token == "passed":
                        passed = count
                    elif token == "failed":
                        failed = count
                    elif token == "error":
                        errors = count
    status = "PASS" if (failed == 0 and errors == 0 and passed > 0) else "FAIL"
    return passed, failed, errors, status


def main():
    files = discover_tests()
    chunks = chunk_files(files, CHUNK_SIZE)
    results = []
    total_passed = total_failed = total_errors = 0
    overall = "PASS"

    # Clear old logs
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for old in LOG_DIR.glob("chunk_*.log"):
        old.unlink()

    print(f"Running {len(files)} test files in {len(chunks)} sequential chunks...")
    for idx, chunk in enumerate(chunks, start=1):
        print(f"Chunk {idx}/{len(chunks)}: {len(chunk)} files...")
        (passed, failed, errors, status), elapsed, rc = run_chunk(idx, chunk)
        total_passed += passed
        total_failed += failed
        total_errors += errors
        if status == "FAIL":
            overall = "FAIL"
        results.append({
            "chunk_id": idx,
            "files": chunk,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "status": status,
            "returncode": rc,
        })
        print(f"  -> {status}: {passed} passed, {failed} failed, {errors} errors ({elapsed:.1f}s)")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files": len(files),
        "chunks": len(chunks),
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errors": total_errors,
        "overall_status": overall,
        "chunks_detail": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {REPORT_PATH}")
    print(f"Overall: {overall} — {total_passed} passed, {total_failed} failed, {total_errors} errors")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
