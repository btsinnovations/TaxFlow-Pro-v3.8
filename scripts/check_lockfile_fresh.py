"""Pre-commit hook: ensure requirements-lock.txt is newer than requirements.txt."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "requirements-lock.txt"
REQ = ROOT / "requirements.txt"


def main() -> int:
    if not LOCK.exists():
        print("requirements-lock.txt is missing; regenerate it.", file=sys.stderr)
        return 1
    if not REQ.exists():
        print("requirements.txt is missing.", file=sys.stderr)
        return 1
    lock_mtime = LOCK.stat().st_mtime
    req_mtime = REQ.stat().st_mtime
    if req_mtime > lock_mtime:
        print(
            "requirements.txt is newer than requirements-lock.txt; "
            "regenerate the lockfile and commit both files.",
            file=sys.stderr,
        )
        return 1
    print("requirements-lock.txt is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
