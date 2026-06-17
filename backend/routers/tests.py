import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/tests", tags=["tests"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Fast, stable smoke tests displayed in the frontend TestSuite panel by default.
# These do not require live external services and complete in under a second.
DEFAULT_TEST_TARGETS = [
    "tests/test_graph.py",
    "tests/test_identity.py",
    "tests/test_invariants.py",
    "tests/test_normalization.py",
    "tests/test_ml_fallback.py",
    "tests/test_parsers.py",
    "tests/test_split.py",
    "tests/test_tax.py",
    "backend/tests/test_depreciation.py",
    "backend/tests/test_ofx_client.py",
    "backend/tests/test_parser_unification.py",
]

# Map a test file name to the high-level category used by the frontend.
_CATEGORY_RULES = [
    ("security", "Security"),
    ("test_api", "Security"),
    ("test_ofx_client", "Export"),
    ("export", "Export"),
    ("test_depreciation", "Tax Rule"),
    ("tax", "Tax Rule"),
    ("categorizer", "ML"),
    ("ml_", "ML"),
    ("invariant", "Fragility"),
    ("identity", "Fragility"),
    ("graph", "Fragility"),
    ("aliases", "Fragility"),
    ("fragility", "Fragility"),
    ("parser", "Parser"),
    ("normalization", "Parser"),
]

_STATUS_MAP = {
    "PASSED": "PASS",
    "FAILED": "FAIL",
    "SKIPPED": "SKIP",
    "ERROR": "FAIL",
}

_TEST_LINE_RE = re.compile(
    r"^(?P<file>.+?\.py)::(?P<node>.+?)\s+(?P<status>PASSED|FAILED|SKIPPED|ERROR)(?:\s+\[[^\]]+\])?(?:\s+(?P<reason>.*))?$"
)
_SUMMARY_RE = re.compile(r"^=+\s+(short test summary|ERRORS|PASSES|FAILURES|warnings summary)")


def _category_for_path(file_path: str) -> str:
    filename = os.path.basename(file_path).lower()
    for key, category in _CATEGORY_RULES:
        if key in filename:
            return category
    return "Parser"


def _parse_pytest_output(stdout: str) -> List[Dict[str, str]]:
    """Parse `pytest -v --tb=short` output into frontend-friendly test records."""
    results: List[Dict[str, str]] = []
    lines = stdout.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if _SUMMARY_RE.match(line) or line.strip().startswith("short test summary"):
            break

        match = _TEST_LINE_RE.match(line)
        if not match:
            i += 1
            continue

        file_path = match.group("file")
        node = match.group("node")
        status = _STATUS_MAP.get(match.group("status"), "FAIL")
        reason = (match.group("reason") or "").strip()

        details = reason or ""
        # For failures, collect the short traceback that follows.
        if status == "FAIL":
            detail_lines: List[str] = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if _TEST_LINE_RE.match(next_line) or _SUMMARY_RE.match(next_line):
                    break
                if next_line.strip() and not next_line.startswith(" "):
                    # Likely a new unrelated message; stop collecting.
                    break
                detail_lines.append(next_line.rstrip())
                j += 1
            if detail_lines:
                details = "\n".join(detail_lines).strip() or details
            i = j - 1

        name = f"{file_path}::{node}"
        results.append(
            {
                "name": name,
                "category": _category_for_path(file_path),
                "status": status,
                "duration": "",
                "details": details,
            }
        )
        i += 1

    return results


def _run_pytest(full: bool = False) -> Dict[str, Any]:
    targets = ["tests/", "backend/tests/"] if full else DEFAULT_TEST_TARGETS
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *targets,
        "-v",
        "--tb=short",
        "--no-header",
    ]
    timeout = 180 if full else 60
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "error": f"Test run exceeded {timeout} seconds",
            "results": [],
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "last_run": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "results": [],
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "last_run": datetime.now(timezone.utc).isoformat(),
        }

    results = _parse_pytest_output(result.stdout)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    return {
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "results": results,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": len(results),
        "last_run": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/")
def list_tests(request: Request, full: bool = False):
    """Return the latest pytest result set for display in the TestSuite panel."""
    return _run_pytest(full=full)


@router.post("/run")
def run_tests(request: Request, full: bool = False):
    """Trigger a fresh pytest run and return the parsed result set."""
    return _run_pytest(full=full)
