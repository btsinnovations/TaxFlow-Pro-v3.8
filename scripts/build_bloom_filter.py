"""Build a Bloom filter from a newline-delimited breach word list.

Usage:
    python scripts/build_bloom_filter.py data/breach-passwords.txt data/breach-bloom.json

The output JSON is consumed by `backend.security.breach_bloom`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on PYTHONPATH so `backend` imports work.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.security.breach_bloom import BloomFilter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a breach Bloom filter.")
    parser.add_argument("input", help="Path to newline-delimited password file")
    parser.add_argument("output", help="Path for the output JSON bloom filter")
    parser.add_argument("--capacity", type=int, default=100_000, help="Expected number of items")
    parser.add_argument("--fpr", type=float, default=0.001, help="Target false-positive rate")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    words = [line.strip().lower() for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    bloom = BloomFilter(capacity=max(args.capacity, len(words)), false_positive_rate=args.fpr)
    bloom.update(words)
    bloom.save(args.output)
    print(f"Saved bloom filter with {bloom.count} items to {args.output}")
    print(f"  size={bloom.size} bits, hashes={bloom.hashes}, fpr≈{args.fpr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
