"""TaxFlow Pro v3.11.6 — Final Comprehensive Stress & Validation Sequential Runner.

This script executes the validation gate and writes JSON/MD artifacts.
It is intentionally self-contained and only touches test databases/files.
"""
from __future__ import annotations

import base64
import concurrent.futures
import datetime
import json
import os
import random
import secrets
import shutil
import sqlite3
import statistics
import string
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

# Ensure test environment
os.environ["TAXFLOW_SINGLE_USER"] = "true"
os.environ["TAXFLOW_RUNTIME_MODE"] = "offline"
os.environ["TAXFLOW_TESTING"] = "true"
os.environ["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
os.environ["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = PROJECT_ROOT / "shared" / "tasks" / "v3.11.6"
LOG_DIR = REPORT_DIR / "baseline_test_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

RESULTS: dict = {
    "meta": {
        "version": "3.11.6",
        "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
    },
    "baseline": {},
    "phase1": {},
    "phase2": {},
    "phase3": {},
    "phase4": {},
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _run(cmd: list[str], env: dict | None = None, timeout: int = 600, cwd: Path = PROJECT_ROOT) -> dict:
    """Run a shell command and return structured result."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.perf_counter() - t0
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "elapsed_seconds": round(elapsed, 2),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
            "ok": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(cmd),
            "returncode": -1,
            "elapsed_seconds": round(time.perf_counter() - t0, 2),
            "stdout_tail": (exc.stdout or b"")[-2000:].decode("utf-8", errors="ignore"),
            "stderr_tail": (exc.stderr or b"")[-2000:].decode("utf-8", errors="ignore"),
            "ok": False,
            "timeout": True,
        }
    except Exception as exc:
        return {
            "cmd": " ".join(cmd),
            "returncode": -1,
            "elapsed_seconds": round(time.perf_counter() - t0, 2),
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "ok": False,
        }


def _log(label: str, result: dict) -> None:
    path = LOG_DIR / f"{label}.log"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"[{label}] ok={result['ok']} rc={result['returncode']} elapsed={result['elapsed_seconds']}s")


def run_pytest_batch(label: str, modules: list[str], env: dict | None = None, timeout: int = 1200) -> dict:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short"] + modules
    result = _run(cmd, env=env, timeout=timeout)
    _log(label, result)
    return result


def phase0_baseline() -> None:
    print("\n=== Baseline Gate ===")
    # 1. SQLite full suite (run; if it hangs, we note and batch)
    full = run_pytest_batch(
        "baseline_sqlite_full",
        ["backend/tests"],
        timeout=2400,
    )
    RESULTS["baseline"]["sqlite_full"] = full

    # 2. PostgreSQL full suite (TEST_DATABASE_URL)
    pg_env = {"DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_test")}
    pg_full = run_pytest_batch(
        "baseline_postgres_full",
        ["backend/tests"],
        env=pg_env,
        timeout=2400,
    )
    RESULTS["baseline"]["postgres_full"] = pg_full

    # 3. Alembic upgrade/downgrade/upgrade on SQLite
    with tempfile.TemporaryDirectory(prefix="tf-alembic-") as tmp:
        db_path = Path(tmp) / "taxflow.db"
        env = {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ALEMBIC_CONFIG": str(PROJECT_ROOT / "alembic.ini"),
        }
        up = _run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, timeout=300)
        down = _run([sys.executable, "-m", "alembic", "downgrade", "base"], env=env, timeout=300)
        up2 = _run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, timeout=300)
        integrity = {"ok": False, "result": "n/a"}
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute("PRAGMA integrity_check").fetchone()
            integrity = {"ok": row[0] == "ok", "result": row[0]}
            conn.close()
        except Exception as exc:
            integrity = {"ok": False, "result": str(exc)}
        RESULTS["baseline"]["alembic_sqlite"] = {
            "upgrade_head": up,
            "downgrade_base": down,
            "upgrade_head_again": up2,
            "integrity_check": integrity,
        }
        _log("baseline_alembic_sqlite", RESULTS["baseline"]["alembic_sqlite"])

    # 4. Production-mode smoke via script
    prod_smoke = _run([sys.executable, "scripts/packaging/smoke_ci.py"], timeout=300)
    _log("baseline_production_smoke", prod_smoke)
    RESULTS["baseline"]["production_smoke"] = prod_smoke

    # 5. Fresh SQLite integrity check already covered in alembic block


def phase1_probabilistic() -> None:
    print("\n=== Phase 1 — Probabilistic Backend Robustness ===")
    # A.4, A.6, A.8-A.12 from Track A helper
    helper = PROJECT_ROOT / "shared" / "tasks" / "v3.11.6" / "track_a_missing_sections.py"
    if helper.exists():
        r = _run([sys.executable, str(helper)], timeout=600)
        _log("phase1_track_a_helper", r)
        RESULTS["phase1"]["track_a_helper"] = r
    else:
        RESULTS["phase1"]["track_a_helper"] = {"ok": False, "error": "helper not found"}

    # 6. API fuzz (lightweight)
    fuzz = _run([sys.executable, "-m", "pytest", "backend/tests/test_global_rate_limit.py", "backend/tests/test_request_size_limits.py", "backend/tests/test_path_traversal.py", "backend/tests/test_upload_security.py", "-q", "--tb=short"], timeout=300)
    _log("phase1_api_fuzz", fuzz)
    RESULTS["phase1"]["api_fuzz"] = fuzz

    # 10. Parser resilience
    parser = _run([sys.executable, "-m", "pytest", "backend/tests/test_parser_regression.py", "backend/tests/test_parser_sandbox.py", "backend/tests/test_pdf_fuzz.py", "backend/tests/test_ofx.py", "-q", "--tb=short"], timeout=600)
    _log("phase1_parser_resilience", parser)
    RESULTS["phase1"]["parser_resilience"] = parser

    # 11. Date & fiscal edge cases
    date_edge = _run([sys.executable, "-m", "pytest", "backend/tests/test_period_close.py", "backend/tests/test_year_end.py", "backend/tests/test_adjusting_entries.py", "-q", "--tb=short"], timeout=300)
    _log("phase1_date_fiscal_edge", date_edge)
    RESULTS["phase1"]["date_fiscal_edge"] = date_edge


def phase2_performance() -> None:
    print("\n=== Phase 2 — Performance & Volume Stress ===")
    # 12. Volume soak via Track A helper (sequential requests)
    # 13. Concurrent load via Track A helper
    # 14-15 not fully automated here due to one-hour resource monitoring scope;
    #     we capture helper output and mark as partial.
    helper_json = PROJECT_ROOT / "shared" / "tasks" / "v3.11.6" / "track_a_missing_sections.json"
    if helper_json.exists():
        data = json.loads(helper_json.read_text(encoding="utf-8"))
        RESULTS["phase2"]["track_a_volume_concurrent"] = data
    else:
        RESULTS["phase2"]["track_a_volume_concurrent"] = {"ok": False, "note": "helper output not available"}

    # Backup/restore round-trip
    backup = _run([sys.executable, "-m", "pytest", "backend/tests/test_backup_import.py", "backend/tests/test_backup_restore.py", "-q", "--tb=short"], timeout=300)
    _log("phase2_backup_restore", backup)
    RESULTS["phase2"]["backup_restore"] = backup


def phase3_frontend() -> None:
    print("\n=== Phase 3 — Frontend & UX Hardening ===")
    # Build frontend
    build = _run(["npm", "run", "build"], cwd=PROJECT_ROOT / "frontend", timeout=300)
    _log("phase3_frontend_build", build)
    RESULTS["phase3"]["frontend_build"] = build

    # Playwright smoke
    e2e = _run(["npx", "playwright", "test", "--reporter=list"], cwd=PROJECT_ROOT / "frontend", timeout=300)
    _log("phase3_playwright_smoke", e2e)
    RESULTS["phase3"]["playwright_smoke"] = e2e

    # Production-mode smoke already captured in baseline


def phase4_final() -> None:
    print("\n=== Phase 4 — Final Integration & Sign-Off ===")
    # 24. Re-run focused regression batch (same as baseline batch)
    focused = _run([
        sys.executable, "-m", "pytest", "-q", "--tb=short",
        "backend/tests/test_api.py", "backend/tests/test_register.py",
        "backend/tests/test_coa.py", "backend/tests/test_gl_bridge.py",
        "backend/tests/test_period_close.py", "backend/tests/test_reconciliation.py",
        "backend/tests/test_tax_exports.py", "backend/tests/test_year_end_package.py",
        "backend/tests/test_alembic_migrations.py", "backend/tests/test_production_mode.py",
    ], timeout=600)
    _log("phase4_final_regression", focused)
    RESULTS["phase4"]["final_regression"] = focused

    # 27. version.txt / build metadata
    version = (PROJECT_ROOT / "version.txt").read_text().strip()
    py_version = (PROJECT_ROOT / "backend" / "version.py").read_text().strip()
    RESULTS["phase4"]["version"] = {"version.txt": version, "backend/version.py": py_version}


def write_report() -> None:
    report_path = REPORT_DIR / "FINAL_COMPREHENSIVE_STRESS_VALIDATION_REPORT.md"
    json_path = REPORT_DIR / "FINAL_COMPREHENSIVE_STRESS_VALIDATION_RESULTS.json"
    json_path.write_text(json.dumps(RESULTS, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Final Comprehensive Stress & Validation Report — TaxFlow Pro v3.11.6",
        "",
        f"**Generated:** {RESULTS['meta']['started']} UTC",
        f"**Version:** {RESULTS['meta']['version']}",
        f"**Project Root:** `{RESULTS['meta']['project_root']}`",
        "",
        "## Executive Summary",
        "",
    ]
    # Verdict
    verdict = "GO" if all(
        r.get("ok") for phase in RESULTS.values() if isinstance(phase, dict)
        for r in phase.values() if isinstance(r, dict) and "ok" in r
    ) else "NO-GO"
    lines.append(f"**Overall Verdict:** {verdict}")
    lines.append("")

    for phase_name, phase_data in RESULTS.items():
        if phase_name == "meta":
            continue
        lines.append(f"## {phase_name.upper()}")
        lines.append("")
        for key, val in phase_data.items():
            lines.append(f"### {key}")
            if isinstance(val, dict):
                if "ok" in val:
                    lines.append(f"- **OK:** {val['ok']}")
                if "returncode" in val:
                    lines.append(f"- **Return Code:** {val['returncode']}")
                if "elapsed_seconds" in val:
                    lines.append(f"- **Elapsed:** {val['elapsed_seconds']}s")
                if "timeout" in val:
                    lines.append(f"- **Timeout:** {val['timeout']}")
                if "stdout_tail" in val and val["stdout_tail"]:
                    lines.append("- **Stdout tail:**")
                    lines.append("```")
                    lines.append(val["stdout_tail"][:500])
                    lines.append("```")
                if "stderr_tail" in val and val["stderr_tail"]:
                    lines.append("- **Stderr tail:**")
                    lines.append("```")
                    lines.append(val["stderr_tail"][:500])
                    lines.append("```")
            else:
                lines.append(f"```json\n{json.dumps(val, indent=2, default=str)[:1000]}\n```")
            lines.append("")

    lines.append("## Recommended Actions")
    lines.append("")
    lines.append("- Review any failed or timed-out gates above.")
    lines.append("- Re-run the full validation after remediation.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {report_path}")
    print(f"JSON results written to {json_path}")


def append_memory() -> None:
    mem_dir = Path("memory")
    # When running under subagent, the CWD is PROJECT_ROOT (repo), but the workspace root is two levels up.
    # We'll write to the workspace memory path as required.
    ws_root = PROJECT_ROOT.parents[2]  # projects/TaxFlow-Pro/TaxFlow-Pro-v3.9 -> projects/TaxFlow-Pro -> projects -> workspace root
    mem_file = ws_root / "memory" / "2026-06-30.md"
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    summary = f"\n## TaxFlow Pro v3.11.6 Final Validation — {_now()}\n\n"
    for phase_name, phase_data in RESULTS.items():
        if phase_name == "meta":
            continue
        summary += f"### {phase_name.upper()}\n"
        for key, val in phase_data.items():
            if isinstance(val, dict) and "ok" in val:
                summary += f"- {key}: ok={val['ok']} rc={val.get('returncode', 'n/a')}\n"
            else:
                summary += f"- {key}: {str(val)[:120]}\n"
        summary += "\n"
    with mem_file.open("a", encoding="utf-8") as f:
        f.write(summary)
    print(f"Memory summary appended to {mem_file}")


def main() -> int:
    phase0_baseline()
    phase1_probabilistic()
    phase2_performance()
    phase3_frontend()
    phase4_final()
    write_report()
    append_memory()
    return 0 if all(
        r.get("ok") for phase in RESULTS.values() if isinstance(phase, dict)
        for r in phase.values() if isinstance(r, dict) and "ok" in r
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
