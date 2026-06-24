"""CLI entry point for the dependency vulnerability scanner (TASK-032).

Usage:
    python scripts/vuln_scan.py [--db PATH] [--output PATH]

Exit codes:
    0 — no vulnerabilities found
    1 — vulnerabilities detected
    2 — scanner error
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "vuln-db.json"


def _run_pip_audit() -> tuple[bool, list[dict]]:
    """Run pip-audit --local and return (succeeded, matches).

    pip-audit exits 1 when vulnerabilities are found, which is a successful
    run from our perspective. We only fall back to the custom DB if the output
    cannot be parsed or stderr indicates a runtime failure.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "--local",
        "--format=json",
        "--desc=off",
        "--progress-spinner=off",
        "-o",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)

    report_text = ""
    try:
        report_text = tmp_path.read_text(encoding="utf-8")
        report = json.loads(report_text)
    except Exception:
        report = None
    finally:
        tmp_path.unlink(missing_ok=True)

    # If we have a parseable report, trust it regardless of exit code.
    if report is not None:
        matches: list[dict] = []
        for dep in report.get("dependencies", []):
            name = dep.get("name")
            version = dep.get("version")
            for vuln in dep.get("vulns", []):
                matches.append(
                    {
                        "package": name,
                        "installed_version": version,
                        "vuln_id": vuln.get("id", "UNKNOWN"),
                        "fix_versions": vuln.get("fix_versions", []),
                        "aliases": vuln.get("aliases", []),
                        "summary": None,
                    }
                )
        return True, matches

    # No parseable report and stderr present → runtime error; fall back.
    if result.stderr.strip():
        print(f"pip-audit runtime error: {result.stderr}", file=sys.stderr)
    return False, []



def _run_custom_scan(db_path: Path) -> list[dict]:
    """Fallback to the offline custom vulnerability database."""
    sys.path.insert(0, str(ROOT))
    from backend.security.vuln_scanner import scan_dependencies, format_report

    matches = scan_dependencies(db_path)
    report = format_report(matches)
    return [
        {
            "package": item["package"],
            "installed_version": item["installed_version"],
            "vuln_id": item["vuln_id"],
            "fix_versions": [],
            "aliases": item["aliases"],
            "summary": item["summary"],
        }
        for item in report.get("matches", [])
    ]


def _format_report(matches: list[dict], source: str) -> dict:
    return {
        "ok": len(matches) == 0,
        "source": source,
        "vulnerable_count": len(matches),
        "matches": matches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan installed Python dependencies for known vulnerabilities."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Path to local vulnerability database JSON used as fallback (default: {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON report to this file (default: stdout).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Ignored: pip-audit --local is already offline-by-default.",
    )
    args = parser.parse_args(argv)

    succeeded, matches = _run_pip_audit()
    source = "pip-audit"
    if not succeeded:
        source = "custom-vuln-db"
        matches = _run_custom_scan(Path(args.db))

    report = _format_report(matches, source)
    report_json = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(report_json + "\n", encoding="utf-8")
    else:
        print(report_json)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
