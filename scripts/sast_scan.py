"""SAST scanner wrapper for TaxFlow Pro (TASK-032).

Runs Bandit against the backend source tree and fails only on high/critical
severity findings by default. A JSON baseline may be supplied to suppress
previously-accepted low/medium noise.

Usage:
    python scripts/sast_scan.py [--baseline PATH] [--output PATH] [--strict]

Exit codes:
    0 - no high/critical findings (or no findings at all when --strict)
    1 - blocking findings detected
    2 - scanner/runtime error
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "bandit-report.json"
BACKEND_DIR = ROOT / "backend"


def _load_baseline(path: Path | None) -> set[str]:
    """Return a set of issue fingerprints to ignore."""
    if path is None or not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    fingerprints: set[str] = set()
    for issue in data.get("results", []):
        fingerprint = issue.get("issue_text", "") + issue.get("filename", "") + str(issue.get("line_number", ""))
        fingerprints.add(fingerprint)
    return fingerprints


def run_bandit(output_path: Path) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "bandit",
        "-r",
        str(BACKEND_DIR),
        "-f",
        "json",
        "-o",
        str(output_path),
        "--exit-zero",  # we decide the exit code ourselves
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode not in (0, 1):
        # Bandit returns 1 when it finds issues even with --exit-zero? Actually
        # --exit-zero forces 0. Unexpected codes indicate runtime errors.
        raise RuntimeError(f"bandit exited {result.returncode}: {result.stderr}")

    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Bandit SAST against backend/ and report high/critical findings."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to a JSON baseline of accepted low/medium findings.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path for the Bandit JSON report (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any severity (default: high/critical only).",
    )
    args = parser.parse_args(argv)

    try:
        report = run_bandit(args.output)
    except Exception as exc:
        print(f"SAST scan failed to run: {exc}", file=sys.stderr)
        return 2

    baseline = _load_baseline(args.baseline)
    severities = {"HIGH", "CRITICAL"} if not args.strict else {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    blocking: list[dict] = []
    for issue in report.get("results", []):
        fingerprint = issue.get("issue_text", "") + issue.get("filename", "") + str(issue.get("line_number", ""))
        if fingerprint in baseline:
            continue
        if issue.get("issue_severity", "").upper() in severities:
            blocking.append(issue)

    summary = {
        "ok": len(blocking) == 0,
        "total_findings": len(report.get("results", [])),
        "blocking_findings": len(blocking),
        "severity_filter": "any" if args.strict else "HIGH/CRITICAL",
        "report_path": str(args.output),
        "blocking": blocking,
    }
    print(json.dumps(summary, indent=2))

    if blocking:
        print(
            f"\n{len(blocking)} blocking SAST finding(s) detected. See {args.output}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
