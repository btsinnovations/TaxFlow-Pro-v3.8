"""Tests for the offline dependency vulnerability scanner."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from backend.security.vuln_scanner import (
    VulnMatch,
    _parse_version,
    _version_in_range,
    scan_dependencies,
    format_report,
)


def test_parse_version_normalizes():
    assert _parse_version("2.31.0") == (2, 31, 0)
    assert _parse_version("42.0.0") == (42, 0, 0)
    assert _parse_version("0.0.6") == (0, 0, 6)
    assert _parse_version("2.31.0rc1") == (2, 31, 0)


def test_version_in_range_simple():
    assert _version_in_range("2.30.0", [">=2.0.0,<2.31.0"])
    assert not _version_in_range("2.31.0", [">=2.0.0,<2.31.0"])
    assert _version_in_range("41.0.0", [">=0.9.0,<42.0.0"])
    assert not _version_in_range("42.0.0", [">=0.9.0,<42.0.0"])


def test_version_in_range_single_bound():
    assert _version_in_range("2.31.0", [">=2.31.0"])
    assert not _version_in_range("2.30.0", [">=2.31.0"])
    assert _version_in_range("0.0.5", ["<=0.0.6"])
    assert not _version_in_range("0.0.7", ["<=0.0.6"])


def test_scan_dependencies_finds_vulnerable_package(monkeypatch):
    db = {
        "vulns": [
            {
                "id": "TEST-CVE-001",
                "package": {"name": "requests"},
                "aliases": ["CVE-TEST-001"],
                "severity": "HIGH",
                "summary": "Test vuln",
                "affected": [
                    {
                        "ranges": [
                            {
                                "type": "ECOSYSTEM",
                                "introduced": "2.0.0",
                                "fixed": "2.31.0",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
        json.dump(db, f)
        f.flush()
        db_path = Path(f.name)

    def fake_installed():
        return {"requests": "2.30.0"}

    monkeypatch.setattr(
        "backend.security.vuln_scanner._installed_packages", fake_installed
    )

    try:
        matches = scan_dependencies(db_path)
        assert len(matches) == 1
        m = matches[0]
        assert m.package == "requests"
        assert m.installed_version == "2.30.0"
        assert m.vuln_id == "TEST-CVE-001"
        assert m.severity == "HIGH"
    finally:
        db_path.unlink()


def test_scan_dependencies_skips_uninstalled_package(monkeypatch):
    db = {
        "vulns": [
            {
                "id": "TEST-CVE-002",
                "package": {"name": "django"},
                "severity": "CRITICAL",
                "affected": [
                    {
                        "ranges": [
                            {
                                "type": "ECOSYSTEM",
                                "introduced": "0.0.0",
                                "fixed": "5.0.0",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
        json.dump(db, f)
        f.flush()
        db_path = Path(f.name)

    def fake_installed():
        return {"requests": "2.31.0"}

    monkeypatch.setattr(
        "backend.security.vuln_scanner._installed_packages", fake_installed
    )

    try:
        matches = scan_dependencies(db_path)
        assert matches == []
    finally:
        db_path.unlink()


def test_scan_dependencies_skips_fixed_version(monkeypatch):
    db = {
        "vulns": [
            {
                "id": "TEST-CVE-003",
                "package": {"name": "fastapi"},
                "severity": "MEDIUM",
                "affected": [
                    {
                        "ranges": [
                            {
                                "type": "ECOSYSTEM",
                                "introduced": "0.1.0",
                                "fixed": "0.110.0",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
        json.dump(db, f)
        f.flush()
        db_path = Path(f.name)

    def fake_installed():
        return {"fastapi": "0.110.0"}

    monkeypatch.setattr(
        "backend.security.vuln_scanner._installed_packages", fake_installed
    )

    try:
        matches = scan_dependencies(db_path)
        assert matches == []
    finally:
        db_path.unlink()


def test_format_report_empty():
    report = format_report([])
    assert report["ok"] is True
    assert report["vulnerable_count"] == 0
    assert report["matches"] == []


def test_format_report_with_match():
    match = VulnMatch(
        package="requests",
        installed_version="2.30.0",
        vuln_id="TEST-CVE-001",
        affected_ranges=[">=2.0.0,<2.31.0"],
        aliases=["CVE-TEST-001"],
        severity="HIGH",
        summary="Test vuln",
    )
    report = format_report([match])
    assert report["ok"] is False
    assert report["vulnerable_count"] == 1
    assert report["matches"][0]["package"] == "requests"
