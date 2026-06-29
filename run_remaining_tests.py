import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "shared" / "tasks" / "v3.11.6" / "baseline_test_logs"


def run_chunk(chunk_id, files):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"chunk_{chunk_id:03d}.log"
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["TAXFLOW_TESTING"] = "true"
    env["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
    env["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + files
    print(f"Running chunk {chunk_id}: {len(files)} files...")
    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT, text=True)
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        print(f"  chunk {chunk_id} tail:\n" + "\n".join(f.read().splitlines()[-5:]))
    return proc.returncode


if __name__ == "__main__":
    remaining = [
        (7, [
            "backend/tests/test_rls_postgres.py",
            "backend/tests/test_roles.py",
            "backend/tests/test_rules.py",
            "backend/tests/test_sales_tax.py",
            "backend/tests/test_security_headers.py",
            "backend/tests/test_suite_hardening.py",
            "backend/tests/test_tax_exports.py",
            "backend/tests/test_tax_exports_extended.py",
            "backend/tests/test_transactions.py",
        ]),
        (8, [
            "backend/tests/test_trial_balance.py",
            "backend/tests/test_user_profile.py",
            "backend/tests/test_vendor_1099.py",
            "backend/tests/test_vendors.py",
            "backend/tests/test_yaml_safety.py",
            "backend/tests/test_year_end.py",
            "backend/tests/test_year_end_package.py",
            "backend/tests/test_bank_parsers.py",
            "backend/tests/test_institution_detection.py",
            "backend/tests/test_ocr_parser.py",
        ]),
        (9, [
            "backend/tests/test_ofx.py",
            "backend/tests/test_parser_detection.py",
            "backend/tests/test_parser_regression.py",
            "backend/tests/test_parser_sandbox.py",
            "backend/tests/test_parser_unification.py",
        ]),
    ]
    rc = 0
    for chunk_id, files in remaining:
        rc |= run_chunk(chunk_id, files)
    sys.exit(rc)
