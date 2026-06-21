"""Offline self-test and environment validation.

This module checks that TaxFlow Pro can operate without network access and
that all required local dependencies are present and functional.
"""

from __future__ import annotations

import importlib
import os
import socket
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class SelfTestResult:
    name: str
    passed: bool
    message: str
    critical: bool = True


@dataclass
class SelfTestReport:
    results: List[SelfTestResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed or not r.critical for r in self.results)

    @property
    def critical_failures(self) -> List[SelfTestResult]:
        return [r for r in self.results if not r.passed and r.critical]

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "critical_failures": [
                {"name": r.name, "message": r.message} for r in self.critical_failures
            ],
            "results": [
                {"name": r.name, "passed": r.passed, "message": r.message, "critical": r.critical}
                for r in self.results
            ],
        }


def _module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _binary_available(name: str) -> bool:
    try:
        subprocess.run([name, "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _has_network_access(host: str = "8.8.8.8", port: int = 53, timeout: float = 2.0) -> bool:
    """Probe whether the OS can reach the outside world."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_self_test(
    db_path: Optional[Path] = None,
    *,
    require_no_network: bool = False,
) -> SelfTestReport:
    """Run the full offline self-test suite.

    Checks:
      - Required Python packages importable
      - SQLite database accessible and integrity-checkable
      - Tesseract OCR binary available
      - Poppler pdftotext binary available (optional)
      - No unexpected network calls needed at runtime
      - Local encryption primitives functional
    """
    report = SelfTestReport()

    # Required Python packages
    required_modules = [
        ("fastapi", True),
        ("sqlalchemy", True),
        ("cryptography", True),
        ("pdfplumber", True),
        ("pytesseract", True),
        ("PIL", True),
    ]
    for module, critical in required_modules:
        available = _module_available(module)
        report.results.append(
            SelfTestResult(
                name=f"module:{module}",
                passed=available,
                message=f"{module} is {'available' if available else 'MISSING'}",
                critical=critical,
            )
        )

    # Local crypto sanity check
    try:
        from .crypto import LocalCryptoManager

        manager = LocalCryptoManager.create("test-password")
        ciphertext = manager.encrypt(b"hello offline world")
        plaintext = manager.decrypt(ciphertext)
        report.results.append(
            SelfTestResult(
                name="crypto:roundtrip",
                passed=plaintext == b"hello offline world",
                message="Local encryption round-trip succeeded",
                critical=True,
            )
        )
    except Exception as exc:
        report.results.append(
            SelfTestResult(
                name="crypto:roundtrip",
                passed=False,
                message=f"Local encryption failed: {exc}",
                critical=True,
            )
        )

    # SQLite database check
    if db_path is None:
        # Default to the SQLite path configured by the app if any
        db_url = os.environ.get("DATABASE_URL", "sqlite:///./taxflow.db")
        if db_url.startswith("sqlite:///"):
            db_path = Path(db_url.replace("sqlite:///", ""))
        else:
            db_path = Path("taxflow.db")

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            report.results.append(
                SelfTestResult(
                    name="sqlite:integrity",
                    passed=integrity == "ok",
                    message=f"SQLite integrity check: {integrity}",
                    critical=True,
                )
            )
        finally:
            conn.close()
    except Exception as exc:
        report.results.append(
            SelfTestResult(
                name="sqlite:integrity",
                passed=False,
                message=f"SQLite check failed: {exc}",
                critical=True,
            )
        )

    # External binaries
    tesseract_ok = _binary_available("tesseract")
    report.results.append(
        SelfTestResult(
            name="binary:tesseract",
            passed=tesseract_ok,
            message="Tesseract OCR is available" if tesseract_ok else "Tesseract OCR is MISSING",
            critical=True,
        )
    )

    poppler_ok = _binary_available("pdftotext")
    report.results.append(
        SelfTestResult(
            name="binary:poppler",
            passed=poppler_ok,
            message="Poppler pdftotext is available" if poppler_ok else "Poppler pdftotext is MISSING (optional)",
            critical=False,
        )
    )

    # Network probe
    if require_no_network:
        network_ok = not _has_network_access()
        report.results.append(
            SelfTestResult(
                name="network:isolated",
                passed=network_ok,
                message="No outbound network access detected" if network_ok else "Network access detected (offline mode expects none)",
                critical=False,
            )
        )

    return report


def print_report(report: SelfTestReport) -> None:
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        crit = " (critical)" if result.critical else ""
        print(f"[{status}]{crit} {result.name}: {result.message}")
    print(f"\nAll passed: {report.all_passed}")
    if report.critical_failures:
        print("Critical failures:")
        for failure in report.critical_failures:
            print(f"  - {failure.name}: {failure.message}")


if __name__ == "__main__":
    report = run_self_test(require_no_network=False)
    print_report(report)
