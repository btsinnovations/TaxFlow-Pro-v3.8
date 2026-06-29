"""Aggregate results from detached chunked pytest logs."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "shared" / "tasks" / "v3.11.6" / "baseline_test_logs"
REPORT_PATH = ROOT / "shared" / "tasks" / "v3.11.6" / "BASELINE_TEST_REPORT.json"


def parse_log(log_path: Path):
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    passed = failed = errors = 0
    for line in text.splitlines():
        # Match pytest summary lines like "60 passed, 2 failed in 15.37s"
        m = re.search(r"=+\s+([\d\s\w,]+)\s+in\s+[\d.]+s\s*=+", line)
        if m:
            summary = m.group(1)
            # Extract counts
            for token in ["passed", "failed", "error", "errors"]:
                tm = re.search(rf"(\d+)\s+{token}", summary)
                if tm:
                    count = int(tm.group(1))
                    if token in ("passed",):
                        passed = count
                    elif token in ("failed",):
                        failed = count
                    elif token in ("error", "errors"):
                        errors = count
    status = "PASS" if (failed == 0 and errors == 0 and passed >= 0) else "FAIL"
    return passed, failed, errors, status


def main():
    logs = sorted(LOG_DIR.glob("chunk_*.log"))
    if not logs:
        print(f"No logs found in {LOG_DIR}")
        return 1

    total_passed = total_failed = total_errors = 0
    overall = "PASS"
    details = []
    for log in logs:
        p, f, e, s = parse_log(log)
        total_passed += p
        total_failed += f
        total_errors += e
        if s == "FAIL":
            overall = "FAIL"
        details.append({
            "log": str(log.relative_to(ROOT)),
            "passed": p,
            "failed": f,
            "errors": e,
            "status": s,
        })

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if 'time' in globals() else None,
        "logs_found": len(logs),
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errors": total_errors,
        "overall_status": overall,
        "details": details,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Aggregated {len(logs)} logs -> {REPORT_PATH}")
    print(f"Overall: {overall} — {total_passed} passed, {total_failed} failed, {total_errors} errors")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    import time
    sys.exit(main())
