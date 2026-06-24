"""CLI entry point to back up the TaxFlow Pro SQLite database.

Usage:
    python scripts/backup.py [--db-path PATH] [--target-dir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow imports from the project root when running from scripts/ directory.
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root))

from backend.local.backup import backup_db
from backend.database import DATABASE_URL
from backend.security.path_safety import safe_path


def _default_db_path() -> str:
    """Return a default SQLite DB path from env or fallback location."""
    env_url = os.environ.get("DATABASE_URL", DATABASE_URL)
    if env_url.startswith("sqlite:///"):
        # Relative path
        relative = env_url[len("sqlite:///"):]
        return str(Path(relative).resolve())
    raise SystemExit("DATABASE_URL is not a SQLite path; automatic db-path detection unsupported")


def main():
    parser = argparse.ArgumentParser(description="Back up TaxFlow Pro database")
    parser.add_argument(
        "--db-path",
        default=_default_db_path(),
        help="Path to the SQLite database file (default: from DATABASE_URL)",
    )
    parser.add_argument(
        "--target-dir",
        default=os.environ.get("BACKUP_DIR", "backups"),
        help="Directory to write backup into (default: backups/)",
    )
    parser.add_argument(
        "--plaintext",
        action="store_true",
        help="Create an unencrypted plaintext backup (deprecated; migration only)",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    project_root = Path(__file__).resolve().parents[1]
    try:
        target_dir = safe_path(project_root, args.target_dir)
    except ValueError as exc:
        raise SystemExit(f"Invalid target directory: {exc}") from exc

    manifest_path = backup_db(str(db_path), str(target_dir), plaintext=args.plaintext)
    print(manifest_path)


if __name__ == "__main__":
    main()
