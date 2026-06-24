"""Run pytest for a single task and append results to a shared report file.

Usage:
    python scripts/run-task-tests.py TASK-038.10
    python scripts/run-task-tests.py --file backend/tests/test_hybrid_auth.py
    python scripts/run-task-tests.py --all
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "audit_output" / "task-test-report.json"

# Map task labels to pytest selectors. Update as tasks are added.
TASK_SELECTORS = {
    "TASK-038.10": "backend/tests/test_hybrid_auth.py -k keyfile",
    "TASK-038.9": "backend/tests/test_ml_pipeline.py",
    "TASK-038.12": "backend/tests/test_offline_behavior.py",
    "TASK-038.13": "backend/tests/test_crypto.py backend/tests/test_local_first.py",
    "TASK-038.14": "backend/tests/test_single_user_mode.py",
    "TASK-036": "backend/tests/test_secret_handling.py",
    "TASK-037": "backend/tests/test_dependency_confusion.py",
    "TASK-038-ENTROPY": "backend/tests/test_entropy_audit.py",
    "TASK-039": "backend/tests/test_yaml_safety.py",
}


def run_pytest(selector: str, timeout: int = 300) -> dict:
    cmd = [sys.executable, "-m", "pytest"] + selector.split() + ["-q", "--tb=short"]
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "selector": selector,
            "status": "timeout",
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "duration_seconds": timeout,
        }
    duration = time.time() - start
    return {
        "selector": selector,
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:] if result.stdout else "",
        "stderr": result.stderr[-2000:] if result.stderr else "",
        "duration_seconds": round(duration, 2),
    }


def load_report() -> list[dict]:
    if REPORT_PATH.exists():
        try:
            return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def save_report(report: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run task-specific pytest suite")
    parser.add_argument("task", nargs="?", help="Task label (e.g., TASK-038.10)")
    parser.add_argument("--file", help="Explicit pytest file selector")
    parser.add_argument("--all", action="store_true", help="Run full backend/tests + tests suites")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per invocation")
    args = parser.parse_args()

    if args.all:
        selector = "backend/tests tests"
    elif args.file:
        selector = args.file
    elif args.task:
        if args.task not in TASK_SELECTORS:
            print(f"Unknown task: {args.task}. Known tasks: {', '.join(TASK_SELECTORS)}")
            sys.exit(1)
        selector = TASK_SELECTORS[args.task]
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Running: pytest {selector}")
    run = run_pytest(selector, timeout=args.timeout)
    run["task"] = args.task or args.file or "full"
    run["timestamp"] = datetime.now(timezone.utc).isoformat()

    report = load_report()
    report.append(run)
    save_report(report)

    print(run["stdout"])
    if run["stderr"]:
        print(run["stderr"], file=sys.stderr)
    print(f"Status: {run['status']} | Report: {REPORT_PATH}")
    sys.exit(0 if run["returncode"] == 0 else 1)


if __name__ == "__main__":
    main()
