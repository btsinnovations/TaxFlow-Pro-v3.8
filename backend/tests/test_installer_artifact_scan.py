"""Tests for the installer artifact secret scanner (SEC.26 / SEC.27)."""
from __future__ import annotations

import os
import stat
import zipfile
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo

import pytest

from backend.security.installer_artifact_scan import (
    Finding,
    _is_forbidden,
    _scan_zip_like,
    scan_artifact,
    scan_installer_dir,
    main,
)


# ---------------------------------------------------------------------------
# _is_forbidden unit tests
# ---------------------------------------------------------------------------


class TestIsForbidden:
    def test_env_file(self):
        assert _is_forbidden(".env") is not None

    def test_env_in_subdir(self):
        assert _is_forbidden("project/.env") is not None

    def test_local_secret(self):
        assert _is_forbidden(".local_secret") is not None

    def test_local_secret_old(self):
        assert _is_forbidden(".local_secret.old") is not None

    def test_pem_key(self):
        assert _is_forbidden("server.pem") is not None

    def test_private_key(self):
        assert _is_forbidden("id_rsa") is not None

    def test_ed25519_key(self):
        assert _is_forbidden("id_ed25519") is not None

    def test_key_extension(self):
        assert _is_forbidden("secret.key") is not None

    def test_test_directory(self):
        assert _is_forbidden("backend/tests/test_api.py") is not None

    def test_tests_directory(self):
        assert _is_forbidden("tests/conftest.py") is not None

    def test_fixtures_directory(self):
        assert _is_forbidden("fixtures/sample.pdf") is not None

    def test_test_database(self):
        assert _is_forbidden("test_taxflow.db") is not None

    def test_git_directory(self):
        assert _is_forbidden(".git/config") is not None

    def test_gitignore(self):
        assert _is_forbidden(".gitignore") is not None

    def test_alembic_ini(self):
        assert _is_forbidden("alembic.ini") is not None

    def test_pytest_cache(self):
        assert _is_forbidden(".pytest_cache/v/cache/lastfailed") is not None

    def test_pycache(self):
        assert _is_forbidden("__pycache__/module.cpython-314.pyc") is not None

    def test_clean_file(self):
        assert _is_forbidden("main.py") is None

    def test_normal_pdf(self):
        assert _is_forbidden("data/bank_statement.pdf") is None

    def test_test_code_suffix(self):
        # test_.py files are caught by TEST_CODE_SUFFIXES
        assert _is_forbidden("test_auth.py") is not None

    def test_test_code_suffix_underscore(self):
        assert _is_forbidden("auth_test.py") is not None

    def test_non_test_code_suffix(self):
        assert _is_forbidden("auth.py") is None


# ---------------------------------------------------------------------------
# _scan_zip_like unit tests
# ---------------------------------------------------------------------------


class TestScanZipLike:
    def _make_zip(self, entries: dict[str, bytes], unix_modes: dict | None = None) -> BytesIO:
        """Create a zip archive in memory with given filenames and contents."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in entries.items():
                zf.writestr(name, content)
        buf.seek(0)
        return buf

    def test_clean_zip_passes(self):
        buf = self._make_zip({"main.py": "print('hello')", "app/data.db": "data"})
        findings = _scan_zip_like(Path("clean.zip"), buf)
        assert findings == []

    def test_zip_with_env_file(self):
        buf = self._make_zip({".env": "SECRET=abc123", "main.py": "ok"})
        findings = _scan_zip_like(Path("dirty.zip"), buf)
        assert any(f.reason.startswith("forbidden") for f in findings)

    def test_zip_with_pem(self):
        buf = self._make_zip({"certs/server.pem": "-----BEGIN CERTIFICATE-----"})
        findings = _scan_zip_like(Path("certs.zip"), buf)
        assert any("pem" in f.reason.lower() or "forbidden" in f.reason for f in findings)

    def test_zip_with_test_directory(self):
        buf = self._make_zip({"backend/tests/test_api.py": "import pytest"})
        findings = _scan_zip_like(Path("tests.zip"), buf)
        assert any("test" in f.reason.lower() or "forbidden" in f.reason for f in findings)

    def test_zip_with_world_writable_mode(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            info = zipfile.ZipInfo("script.sh")
            info.external_attr = (0o100777 | 0o002) << 16  # world-writable
            zf.writestr(info, "#!/bin/bash\necho hi")
        buf.seek(0)
        findings = _scan_zip_like(Path("modes.zip"), buf)
        assert any("world-writable" in f.reason for f in findings)


# ---------------------------------------------------------------------------
# scan_artifact integration tests
# ---------------------------------------------------------------------------


class TestScanArtifact:
    def test_nonexistent_artifact_fails(self):
        report = scan_artifact(Path("/nonexistent/installer.exe"))
        assert report["scanned"] is True
        assert report["passed"] is False
        assert any("not found" in f["reason"] for f in report["findings"])

    def test_clean_zip_artifact_passes(self, tmp_path):
        zip_path = tmp_path / "clean.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("main.py", "print('hello')")
            zf.writestr("app/data.db", "data")
        report = scan_artifact(zip_path)
        assert report["passed"] is True
        assert report["size"] > 0

    def test_dirty_zip_artifact_fails(self, tmp_path):
        zip_path = tmp_path / "dirty.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(".env", "SECRET=abc123")
            zf.writestr("main.py", "ok")
        report = scan_artifact(zip_path)
        assert report["passed"] is False
        assert len(report["findings"]) > 0

    def test_deb_artifact_scan(self, tmp_path):
        """Test .deb scanning creates a report even for a minimal ar archive."""
        # A valid .deb must start with "!<arch>\n" followed by ar members.
        # We create a minimal one that won't contain forbidden files.
        deb_path = tmp_path / "test.deb"
        # Minimal ar archive: magic + empty member list
        ar_magic = b"!<arch>\n"
        deb_path.write_bytes(ar_magic)
        report = scan_artifact(deb_path)
        # The scan should not crash; whether it passes depends on content.
        assert report["scanned"] is True

    def test_exe_artifact_scan(self, tmp_path):
        """NSIS .exe installers are zip-based; verify scan doesn't crash."""
        exe_path = tmp_path / "setup.exe"
        with zipfile.ZipFile(exe_path, "w") as zf:
            zf.writestr("app/main.py", "print('TaxFlow Pro')")
        report = scan_artifact(exe_path)
        assert report["scanned"] is True


# ---------------------------------------------------------------------------
# scan_installer_dir integration tests
# ---------------------------------------------------------------------------


class TestScanInstallerDir:
    def test_nonexistent_dir_returns_empty(self):
        reports = scan_installer_dir(Path("/nonexistent/dir"))
        assert reports == []

    def test_empty_dir_returns_empty(self, tmp_path):
        reports = scan_installer_dir(tmp_path)
        assert reports == []

    def test_scans_all_extensions(self, tmp_path):
        # Create minimal zip-based artifacts for each extension
        for ext in [".zip", ".exe"]:
            p = tmp_path / f"test{ext}"
            with zipfile.ZipFile(p, "w") as zf:
                zf.writestr("app/main.py", "print('ok')")
            # .deb, .dmg, .tar.gz need real archives; skip those for simplicity
        for ext in [".deb", ".dmg", ".tar.gz", ".tgz"]:
            p = tmp_path / f"test{ext}"
            p.write_bytes(b"\x00" * 100)

        reports = scan_installer_dir(tmp_path)
        # At least the zip-based ones should be scanned
        assert len(reports) >= 2


# ---------------------------------------------------------------------------
# CLI main() tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_main_no_artifacts_returns_zero(self, tmp_path):
        assert main([str(tmp_path)]) == 0

    def test_main_fail_on_missing(self, tmp_path):
        assert main([str(tmp_path), "--fail-on-missing"]) == 1

    def test_main_with_clean_artifact(self, tmp_path):
        zip_path = tmp_path / "clean.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app/main.py", "ok")
        assert main([str(tmp_path)]) == 0

    def test_main_with_dirty_artifact(self, tmp_path):
        zip_path = tmp_path / "dirty.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(".env", "SECRET=abc")
        assert main([str(tmp_path)]) == 1

    def test_main_single_file(self, tmp_path):
        zip_path = tmp_path / "single.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("README.md", "hello")
        assert main([str(zip_path)]) == 0


# ---------------------------------------------------------------------------
# Finding repr test
# ---------------------------------------------------------------------------


class TestFinding:
    def test_repr(self):
        f = Finding(Path("test.zip"), ".env", "forbidden file: .env")
        assert "test.zip" in repr(f)
        assert ".env" in repr(f)