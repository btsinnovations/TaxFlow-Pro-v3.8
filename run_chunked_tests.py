"""Chunked pytest runner for the full backend test suite.

Splits backend/tests/test_*.py files into chunks and runs each chunk in a
separate subprocess to avoid OpenClaw's ~230s runtime watchdog. Aggregates
results into a JSON report.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent
TESTS_DIR = ROOT / "backend" / "tests"
REPORT_PATH = ROOT / "shared" / "tasks" / "v3.11.6" / "BASELINE_TEST_REPORT.json"
LOG_DIR = ROOT / "shared" / "tasks" / "v3.11.6" / "baseline_test_logs"
CHUNK_SIZE = 10


def discover_tests() -> List[str]:
    files = sorted(TESTS_DIR.glob("test_*.py"))
    return [str(f.relative_to(ROOT)) for f in files]


def chunk_files(files: List[str], size: int) -> List[List[str]]:
    return [files[i : i + size] for i in range(0, len(files), size)]


def run_chunk(chunk_id: int, files: List[str]) -> Tuple[int, int, int, float, str]:
    log_path = LOG_DIR / f"chunk_{chunk_id:03d}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["TAXFLOW_TESTING"] = "true"
    env["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
    env["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # PostgreSQL tests need TEST_DATABASE_URL; keep it if set.
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + files
    start = time.time()
    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    elapsed = time.time() - start
    return parse_chunk_result(log_path, proc.returncode, elapsed)


def parse_chunk_result(log_path: Path, returncode: int, elapsed: float) -> Tuple[int, int, int, float, str]:
    passed, failed, errors = 0, 0, 0
    summary_lines = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
            for line in text.splitlines():
                if " passed" in line and "failed" in line:
                    summary_lines.append(line.strip())
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "passed":
                            passed += int(parts[i - 1])
                        if p == "failed":
                            failed += int(parts[i - 1])
                        if p == "error":
                            errors += int(parts[i - 1])
                elif " passed" in line and line.strip().startswith("="):
                    summary_lines.append(line.strip())
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "passed":
                            passed += int(parts[i - 1])
                        if p == "failed":
                            failed += int(parts[i - 1])
                        if p == "error":
                            errors += int(parts[i - 1])
    except Exception as exc:
        summary_lines.append(f"Could not parse log: {exc}")
    status = "PASS" if returncode == 0 else "FAIL"
    return passed, failed, errors, elapsed, status


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk", type=int, default=None, help="Run only this chunk (1-based)")
    args = parser.parse_args()

    files = discover_tests()
    chunks = chunk_files(files, CHUNK_SIZE)

    if args.chunk is not None:
        idx = args.chunk - 1
        if idx < 0 or idx >= len(chunks):
            print(f"Invalid chunk {args.chunk}; valid range 1..{len(chunks)}")
            return 1
        chunk = chunks[idx]
        print(f"Running chunk {args.chunk}/{len(chunks)}: {len(chunk)} files...")
        passed, failed, errors, elapsed, status = run_chunk(args.chunk, chunk)
        print(f" -> {status}: {passed} passed, {failed} failed, {errors} errors ({elapsed:.1f}s)")
        return 0 if status == "PASS" else 1

    results = []
    total_passed = 0
    total_failed = 0
    total_errors = 0
    overall_status = "PASS"

    print(f"Running {len(files)} test files in {len(chunks)} chunks of up to {CHUNK_SIZE} files each.")

    for idx, chunk in enumerate(chunks, start=1):
        print(f"Chunk {idx}/{len(chunks)}: {len(chunk)} files...")
        passed, failed, errors, elapsed, status = run_chunk(idx, chunk)
        total_passed += passed
        total_failed += failed
        total_errors += errors
        if status == "FAIL":
            overall_status = "FAIL"
        results.append({
            "chunk_id": idx,
            "files": chunk,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "elapsed_seconds": round(elapsed, 2),
            "status": status,
        })
        print(f"  -> {status}: {passed} passed, {failed} failed, {errors} errors ({elapsed:.1f}s)")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files": len(files),
        "chunks": len(chunks),
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errors": total_errors,
        "overall_status": overall_status,
        "chunks_detail": results,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")
    print(f"Overall: {overall_status} — {total_passed} passed, {total_failed} failed, {total_errors} errors")
    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
