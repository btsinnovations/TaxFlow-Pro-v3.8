"""Tests for local secret file permissions and fallback path (TASK-038.13)."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from backend.local.keyring_secret import (
    _local_secret_file,
    _set_secret_file_permissions,
    _write_file_secret,
    store_secret,
)


try:
    import win32api  # type: ignore
except Exception:  # pragma: no cover
    win32api = None  # type: ignore


class TestLocalSecretFilePermissions:
    def test_secret_file_is_written_inside_local_root(self, tmp_path, monkeypatch):
        """The plaintext fallback secret must live inside LOCAL_ROOT."""
        monkeypatch.setattr(
            "backend.local.keyring_secret._local_secret_file",
            lambda: tmp_path / ".local_secret",
        )
        _write_file_secret("test-secret-value")
        secret_path = tmp_path / ".local_secret"
        assert secret_path.exists()
        assert secret_path.read_text().strip() == "test-secret-value"

    def test_secret_file_posix_restrictive_mode(self, tmp_path, monkeypatch):
        if os.name != "posix":
            pytest.skip("POSIX-only test")

        secret_path = tmp_path / ".local_secret"
        secret_path.write_text("x")
        _set_secret_file_permissions(secret_path)
        mode = stat.S_IMODE(secret_path.stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got 0o{mode:o}"

    def test_secret_file_not_world_readable_on_windows(self, tmp_path, monkeypatch):
        if os.name != "nt":
            pytest.skip("Windows-only test")

        # Conftest disables keyring, so store_secret falls back to file.
        monkeypatch.setattr(
            "backend.local.keyring_secret._local_secret_file",
            lambda: tmp_path / ".local_secret",
        )
        store_secret("test-secret-value")
        secret_path = tmp_path / ".local_secret"
        assert secret_path.exists()

        # Ensure the path is resolved and inside the temp directory.
        assert Path(secret_path).resolve().is_relative_to(tmp_path.resolve())

        # If pywin32 is available, check that no inherited ACL allows other users.
        try:
            import win32security  # type: ignore
            import ntsecuritycon as con  # type: ignore
        except Exception:
            pytest.skip("pywin32 not available")

        sd = win32security.GetFileSecurity(
            str(secret_path.resolve()), win32security.DACL_SECURITY_INFORMATION
        )
        dacl = sd.GetSecurityDescriptorDacl()
        extra_access = False
        username = win32api.GetUserName()
        for i in range(dacl.GetAceCount()):
            ace = dacl.GetAce(i)
            try:
                (ace_type, ace_flags), mask, sid = ace
            except Exception:
                continue
            name, _, _ = win32security.LookupAccountSid(None, sid)
            if name.lower() != username.lower():
                if mask & con.FILE_GENERIC_READ:
                    extra_access = True
                    break
        assert not extra_access, "Local secret file grants read access to another user"
