"""Tests for the offline secret scanner."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from scripts.secret_scan import (
    SecretFinding,
    _scan_file,
    _scan,
    _default_patterns,
    main,
)


ROOT = Path(__file__).resolve().parents[2]


def test_default_patterns_loaded_from_env(monkeypatch):
    monkeypatch.setenv("TAXFLOW_SECRET_PATTERNS", "foo,bar")
    assert _default_patterns() == ["foo", "bar"]


def test_scan_file_flags_secret_assignment(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("api_key = 'sk-1234567890abcdef'\n", encoding="utf-8")
    findings = _scan_file(f, _default_patterns())
    assert len(findings) == 1
    assert findings[0].reason == "suspicious secret assignment"


def test_scan_file_ignores_placeholder(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("api_key = 'YOUR_API_KEY_HERE'\n", encoding="utf-8")
    assert _scan_file(f, _default_patterns()) == []


def test_scan_file_ignores_allowlisted(tmp_path, monkeypatch):
    f = tmp_path / "keyring_secret.py"
    f.write_text("secret_key = 'super-secret-value-12345'\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.secret_scan._is_allowlisted", lambda p: str(p.name) == "keyring_secret.py"
    )
    assert _scan_file(f, _default_patterns()) == []


def test_scan_directory(tmp_path):
    (tmp_path / "a.py").write_text("password = 'hunter2'\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("no secrets here\n", encoding="utf-8")
    findings = _scan([str(tmp_path)], _default_patterns())
    assert len(findings) >= 1
    assert any("a.py" in f.path for f in findings)


def test_scan_skips_binary_extension(tmp_path):
    f = tmp_path / "dump.pyc"
    f.write_bytes(b"api_key='supersecret'")
    assert _scan_file(f, _default_patterns()) == []


def test_main_returns_zero_when_clean(tmp_path, monkeypatch, capsys):
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("TAXFLOW_SECRET_SCAN_FAIL", "true")
    rc = main([str(f)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "No potential secrets found" in captured.out


def test_main_returns_one_when_fail_enabled(tmp_path, monkeypatch, capsys):
    f = tmp_path / "dirty.py"
    f.write_text("api_key = 'sk-1234567890abcdef'\n", encoding="utf-8")
    monkeypatch.setenv("TAXFLOW_SECRET_SCAN_FAIL", "true")
    rc = main([str(f), "--fail"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "suspicious secret assignment" in captured.out


def test_main_json_mode(tmp_path, capsys):
    f = tmp_path / "dirty.py"
    f.write_text("api_key = 'sk-1234567890abcdef'\n", encoding="utf-8")
    rc = main([str(f), "--json"])
    captured = capsys.readouterr()
    assert rc == 0  # no --fail
    assert '"ok": false' in captured.out
