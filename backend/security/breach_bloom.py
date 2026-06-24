"""Offline Bloom filter for common password breach detection.

This module is intentionally dependency-free. It implements a simple counting Bloom
filter backed by a JSON-serialisable structure and uses a tiny built-in word list
for the default seed. Production deployments can load a larger filter from disk
via `TAXFLOW_BREACH_BLOOM_PATH` and regenerate it with `scripts/build_bloom_filter.py`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Iterable


DEFAULT_FALSE_POSITIVE_RATE = 0.001
DEFAULT_CAPACITY = 100_000


class BloomFilter:
    """Counting-style Bloom filter with murmur-like hashing via SHA-256 slices.

    Supports serialisation to/from JSON and can be updated in-place.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        false_positive_rate: float = DEFAULT_FALSE_POSITIVE_RATE,
        bits: list[int] | None = None,
        hashes: int | None = None,
        size: int | None = None,
        count: int = 0,
    ):
        self.capacity = max(1, capacity)
        self.false_positive_rate = max(1e-9, min(0.5, false_positive_rate))
        if bits is not None and size is not None and hashes is not None:
            self.size = size
            self.hashes = hashes
            self.bits = bits
        else:
            self.size = self._optimal_size(self.capacity, self.false_positive_rate)
            self.hashes = self._optimal_hashes(self.size, self.capacity)
            self.bits = [0] * ((self.size + 31) // 32)
        self.count = count

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return max(1, int(-(n * math.log(p)) / (math.log(2) ** 2)))

    @staticmethod
    def _optimal_hashes(m: int, n: int) -> int:
        return max(1, round((m / n) * math.log(2)))

    def _hash_indexes(self, item: str) -> list[int]:
        """Return k bit indexes for the UTF-8 encoded item."""
        raw = item.encode("utf-8")
        # Generate as many 32-bit slices as we need from a single SHA-256 digest.
        digest = hashlib.sha256(raw).digest()
        indexes: list[int] = []
        for i in range(self.hashes):
            offset = (i * 4) % len(digest)
            val = int.from_bytes(digest[offset : offset + 4], "big")
            indexes.append(val % self.size)
            if (i + 1) * 4 > len(digest):
                # Re-hash with a different salt if we ever need more than 64 bits.
                digest = hashlib.sha256(digest + raw).digest()
        return indexes

    def _get_bit(self, idx: int) -> int:
        word = idx // 32
        bit = idx % 32
        return (self.bits[word] >> bit) & 1

    def _set_bit(self, idx: int) -> None:
        word = idx // 32
        bit = idx % 32
        self.bits[word] |= 1 << bit

    def add(self, item: str) -> None:
        for idx in self._hash_indexes(item):
            self._set_bit(idx)
        self.count += 1

    def update(self, items: Iterable[str]) -> None:
        for item in items:
            self.add(item)

    def __contains__(self, item: str) -> bool:
        return all(self._get_bit(idx) for idx in self._hash_indexes(item))

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "capacity": self.capacity,
            "false_positive_rate": self.false_positive_rate,
            "size": self.size,
            "hashes": self.hashes,
            "count": self.count,
            "bits": self.bits,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BloomFilter":
        return cls(
            capacity=data.get("capacity", DEFAULT_CAPACITY),
            false_positive_rate=data.get("false_positive_rate", DEFAULT_FALSE_POSITIVE_RATE),
            size=data.get("size"),
            hashes=data.get("hashes"),
            bits=data.get("bits"),
            count=data.get("count", 0),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "BloomFilter":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _default_wordlist() -> list[str]:
    """Built-in mini breach list for offline first-run safety.

    These are extremely common credentials. A real deployment should load a much
    larger filter from disk via `TAXFLOW_BREACH_BLOOM_PATH`.
    """
    return [
        "123456", "123456789", "12345", "password", "password1", "password123",
        "qwerty", "qwerty123", "12345678", "111111", "abc123", "letmein",
        "welcome", "monkey", "1234567890", "sunshine", "princess", "admin",
        "admin123", "root", "login", "changeme", "default", "iloveyou",
        "trustno1", "baseball", "football", "superman", "batman", "hunter",
        "ranger", "thomas", "robert", "michael", "jordan", "maggie", "buster",
        "daniel", "andrew", "joshua", "josh", "james", "dragon", "master",
        "mustang", "shadow", "ashley", "bailey", "mike", "football1", "baseball1",
        "1q2w3e4r", "1qaz2wsx", "zaq12wsx", "!@#$%^&*", "charlie", "aa12345678",
        "senha", "internet", "whatever", "starwars", "trustno1", "princess1",
        "letmein1", "welcome1", "monkey1", "dragon1", "sunshine1", "password!",
        "Password1", "Password123", "Qwerty123", "Admin123", "Root123",
    ]


def get_breach_bloom_filter(path: str | None = None) -> BloomFilter:
    """Load the configured breach bloom filter, or build a default one."""
    env_path = path or os.environ.get("TAXFLOW_BREACH_BLOOM_PATH")
    if env_path and Path(env_path).exists():
        return BloomFilter.load(env_path)
    bloom = BloomFilter(capacity=10_000, false_positive_rate=0.001)
    bloom.update(_default_wordlist())
    return bloom


def is_breached(password: str, path: str | None = None) -> bool:
    """Return True if the password is likely present in the breach bloom filter."""
    bloom = get_breach_bloom_filter(path)
    return password.lower() in bloom
