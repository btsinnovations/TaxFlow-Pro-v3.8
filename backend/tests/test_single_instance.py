"""Tests for single-instance enforcement (B7.01)."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.local.single_instance import (
    acquire_or_exit,
    check_single_instance,
    cleanup_on_exit,
    is_port_bound,
    is_process_alive,
    is_port_responsive,
    read_lock,
    remove_lock,
    write_lock,
    DEFAULT_HOST,
    DEFAULT_PORT,
    LOCK_FILENAME,
)


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Temporary LOCAL_ROOT for lock files."""
    return tmp_path


def test_write_and_read_lock(tmp_root: Path):
    path = write_lock(tmp_root)
    assert path.exists()
    lock = read_lock(tmp_root)
    assert lock is not None
    assert lock["pid"] == os.getpid()
    assert lock["host"] == DEFAULT_HOST
    assert lock["port"] == DEFAULT_PORT


def test_read_lock_missing(tmp_root: Path):
    assert read_lock(tmp_root) is None


def test_read_lock_corrupt(tmp_root: Path):
    (tmp_root / LOCK_FILENAME).write_text("not a number\n", encoding="utf-8")
    assert read_lock(tmp_root) is None


def test_remove_lock(tmp_root: Path):
    write_lock(tmp_root)
    remove_lock(tmp_root)
    assert not (tmp_root / LOCK_FILENAME).exists()


def test_remove_lock_idempotent(tmp_root: Path):
    remove_lock(tmp_root)


def test_is_process_alive_self():
    assert is_process_alive(os.getpid()) is True


def test_is_process_alive_invalid():
    assert is_process_alive(-1) is False


def test_is_process_alive_dead():
    assert is_process_alive(0) is False


def test_is_port_bound_free():
    with patch("socket.socket") as mock_sock:
        instance = mock_sock.return_value.__enter__.return_value
        instance.bind = mock_sock.return_value.bind
        result = is_port_bound("127.0.0.1", 59999)
    assert result is False


def test_is_port_bound_occupied():
    with patch("socket.socket") as mock_sock:
        instance = mock_sock.return_value.__enter__.return_value
        instance.bind.side_effect = OSError("already bound")
        result = is_port_bound("127.0.0.1", 59999)
    assert result is True


def test_is_port_responsive_no_server():
    with patch("socket.create_connection", side_effect=ConnectionRefusedError):
        assert is_port_responsive("127.0.0.1", 59999, timeout=0.5) is False


def test_check_no_lock_no_port(tmp_root: Path):
    with patch("backend.local.single_instance.is_port_bound", return_value=False):
        result = check_single_instance(tmp_root, port=59999)
    assert result["action"] == "proceed"


def test_check_no_lock_port_bound(tmp_root: Path):
    with patch("backend.local.single_instance.is_port_bound", return_value=True):
        result = check_single_instance(tmp_root, port=59999)
    assert result["action"] == "exit"


def test_check_stale_lock(tmp_root: Path):
    (tmp_root / LOCK_FILENAME).write_text("999999\n127.0.0.1\n8000\n", encoding="utf-8")
    with patch("backend.local.single_instance.is_process_alive", return_value=False):
        result = check_single_instance(tmp_root)
    assert result["action"] == "replace"
    assert not (tmp_root / LOCK_FILENAME).exists()


def test_check_alive_responsive(tmp_root: Path):
    write_lock(tmp_root)
    with patch("backend.local.single_instance.is_process_alive", return_value=True), \
         patch("backend.local.single_instance.is_port_responsive", return_value=True), \
         patch("backend.local.single_instance.bring_to_foreground"):
        result = check_single_instance(tmp_root)
    assert result["action"] == "exit"


def test_check_alive_unresponsive(tmp_root: Path):
    write_lock(tmp_root)
    with patch("backend.local.single_instance.is_process_alive", return_value=True), \
         patch("backend.local.single_instance.is_port_responsive", return_value=False), \
         patch("backend.local.single_instance.wait_for_process_exit", return_value=True):
        result = check_single_instance(tmp_root)
    assert result["action"] == "replace"


def test_acquire_proceed(tmp_root: Path):
    with patch("backend.local.single_instance.is_port_bound", return_value=False):
        should_proceed = acquire_or_exit(tmp_root, port=59999)
    assert should_proceed is True
    assert read_lock(tmp_root) is not None


def test_acquire_exit(tmp_root: Path):
    with patch("backend.local.single_instance.is_port_bound", return_value=True):
        should_proceed = acquire_or_exit(tmp_root, port=59999)
    assert should_proceed is False


def test_cleanup_removes_lock(tmp_root: Path):
    write_lock(tmp_root)
    cleanup_on_exit(tmp_root)
    assert not (tmp_root / LOCK_FILENAME).exists()