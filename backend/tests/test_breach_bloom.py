"""Tests for TASK-029: password breach bloom filter integration."""

import os
import tempfile

import pytest

from backend.security.breach_bloom import BloomFilter, get_breach_bloom_filter, is_breached


@pytest.fixture
def tiny_bloom_path(tmp_path):
    bloom = BloomFilter(capacity=100, false_positive_rate=0.001)
    bloom.update(["breached1", "breached2", "123456"])
    path = tmp_path / "bloom.json"
    bloom.save(path)
    return str(path)


def test_bloom_contains_added_items():
    bloom = BloomFilter(capacity=1_000, false_positive_rate=0.001)
    bloom.add("hunter2")
    assert "hunter2" in bloom
    assert "not-present" not in bloom


def test_bloom_round_trip_json(tiny_bloom_path):
    loaded = BloomFilter.load(tiny_bloom_path)
    assert "breached1" in loaded
    assert "breached2" in loaded
    assert "123456" in loaded
    assert "missing" not in loaded


def test_default_filter_catches_common_passwords():
    assert is_breached("123456")
    assert is_breached("password123")
    assert is_breached("qwerty")
    assert not is_breached("S3mi-Fr0nT-P0rtl@nd-7xQ-zZ9")


def test_env_path_overrides_default(tiny_bloom_path, monkeypatch):
    monkeypatch.setenv("TAXFLOW_BREACH_BLOOM_PATH", tiny_bloom_path)
    assert is_breached("breached1")
    assert not is_breached("password123")  # not in the custom filter


def test_get_filter_returns_default_when_path_missing(monkeypatch):
    monkeypatch.setenv("TAXFLOW_BREACH_BLOOM_PATH", "/nonexistent/path.json")
    bloom = get_breach_bloom_filter()
    assert "123456" in bloom


def test_policy_rejects_breached_password(client):
    """Boot with a password known to the default bloom filter should be rejected."""
    from backend.tests.test_hybrid_auth import _reset_db

    _reset_db()
    resp = client.post("/api/auth/boot", json={"password": "password123"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "breach" in str(detail).lower() or "common" in str(detail).lower()


def test_policy_accepts_unbreached_password(client):
    from backend.tests.test_hybrid_auth import _reset_db

    _reset_db()
    resp = client.post(
        "/api/auth/boot",
        json={"password": "T4xFl0w!Br0nze-V@ult-2026"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_build_bloom_filter_script(tmp_path, monkeypatch):
    import sys

    from scripts.build_bloom_filter import main

    wordlist = tmp_path / "words.txt"
    wordlist.write_text("alpha\nbravo\ncharlie\n", encoding="utf-8")
    output = tmp_path / "bloom.json"

    monkeypatch.setattr(sys, "argv", [
        "scripts/build_bloom_filter.py",
        str(wordlist),
        str(output),
    ])
    assert main() == 0
    loaded = BloomFilter.load(output)
    assert "alpha" in loaded
    assert "bravo" in loaded
    assert "charlie" in loaded
    assert "delta" not in loaded
