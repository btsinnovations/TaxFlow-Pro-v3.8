"""Tests for the SAST + SBOM security pipeline (TASK-032).

These tests mock the external scanner CLIs (Bandit, cyclonedx-py, pip-audit)
so the suite stays fast and deterministic regardless of whether the tools are
installed or what vulnerabilities currently exist in the environment.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import scripts.sast_scan as sast_scan
import scripts.sbom_generate as sbom_generate
import scripts.vuln_scan as vuln_scan


class TestSastScan:
    def test_clean_run_returns_zero(self, tmp_path, monkeypatch):
        report_path = tmp_path / "bandit-report.json"
        fake_report = {"results": []}

        def _fake_run_bandit(output_path: Path) -> dict:
            output_path.write_text(json.dumps(fake_report), encoding="utf-8")
            return fake_report

        monkeypatch.setattr(sast_scan, "run_bandit", _fake_run_bandit)
        assert sast_scan.main(["--output", str(report_path)]) == 0
        assert report_path.exists()

    def test_high_severity_fails(self, tmp_path, monkeypatch):
        report_path = tmp_path / "bandit-report.json"
        fake_report = {
            "results": [
                {
                    "issue_text": "hardcoded password",
                    "issue_severity": "HIGH",
                    "filename": "backend/auth.py",
                    "line_number": 42,
                }
            ]
        }

        def _fake_run_bandit(output_path: Path) -> dict:
            output_path.write_text(json.dumps(fake_report), encoding="utf-8")
            return fake_report

        monkeypatch.setattr(sast_scan, "run_bandit", _fake_run_bandit)
        assert sast_scan.main(["--output", str(report_path)]) == 1

    def test_baseline_suppresses_known_issue(self, tmp_path, monkeypatch):
        report_path = tmp_path / "bandit-report.json"
        baseline_path = tmp_path / "baseline.json"
        issue = {
            "issue_text": "hardcoded password",
            "issue_severity": "MEDIUM",
            "filename": "backend/auth.py",
            "line_number": 42,
        }
        baseline_path.write_text(
            json.dumps({"results": [issue]}), encoding="utf-8"
        )
        fake_report = {"results": [issue]}

        def _fake_run_bandit(output_path: Path) -> dict:
            output_path.write_text(json.dumps(fake_report), encoding="utf-8")
            return fake_report

        monkeypatch.setattr(sast_scan, "run_bandit", _fake_run_bandit)
        # MEDIUM alone is not blocking by default; baseline suppresses it.
        assert sast_scan.main([
            "--output", str(report_path),
            "--baseline", str(baseline_path),
            "--strict",
        ]) == 0


class TestSbomGenerate:
    def test_generates_sorted_sbom(self, tmp_path, monkeypatch):
        requirements = tmp_path / "requirements.txt"
        requirements.write_text("z-package>=1.0\na-package>=2.0\n", encoding="utf-8")
        output = tmp_path / "sbom.json"

        fake_sbom = {
            "components": [
                {"name": "z-package", "purl": "pkg:pypi/z-package"},
                {"name": "a-package", "purl": "pkg:pypi/a-package"},
            ]
        }

        def _fake_run(cmd, **kwargs):
            tmp = Path(cmd[-1])
            tmp.write_text(json.dumps(fake_sbom), encoding="utf-8")
            return MagicMock(returncode=0, stderr="")

        monkeypatch.setattr(subprocess, "run", _fake_run)
        assert sbom_generate.generate_sbom(requirements, output) == 0

        bom = json.loads(output.read_text(encoding="utf-8"))
        names = [c["name"] for c in bom["components"]]
        assert names == ["a-package", "z-package"]
        assert bom["metadata"]["tools"]["components"][0]["name"] == "cyclonedx-py"


class TestVulnScan:
    def test_no_vulnerabilities_returns_zero(self, tmp_path, monkeypatch):
        output = tmp_path / "vuln-report.json"

        def _fake_pip_audit():
            return True, []

        monkeypatch.setattr(vuln_scan, "_run_pip_audit", _fake_pip_audit)
        assert vuln_scan.main(["--output", str(output)]) == 0
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["source"] == "pip-audit"
        assert report["ok"] is True

    def test_vulnerabilities_return_one(self, tmp_path, monkeypatch):
        output = tmp_path / "vuln-report.json"

        def _fake_pip_audit():
            return True, [
                {
                    "package": "demo",
                    "installed_version": "1.0.0",
                    "vuln_id": "CVE-2026-0001",
                    "fix_versions": ["1.1.0"],
                    "aliases": [],
                    "summary": None,
                }
            ]

        monkeypatch.setattr(vuln_scan, "_run_pip_audit", _fake_pip_audit)
        assert vuln_scan.main(["--output", str(output)]) == 1
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["vulnerable_count"] == 1

    def test_pip_audit_failure_falls_back(self, tmp_path, monkeypatch):
        output = tmp_path / "vuln-report.json"

        def _fake_pip_audit():
            return False, []

        def _fake_custom_scan(db_path: Path) -> list[dict]:
            return []

        monkeypatch.setattr(vuln_scan, "_run_pip_audit", _fake_pip_audit)
        monkeypatch.setattr(vuln_scan, "_run_custom_scan", _fake_custom_scan)
        assert vuln_scan.main(["--output", str(output)]) == 0
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["source"] == "custom-vuln-db"
