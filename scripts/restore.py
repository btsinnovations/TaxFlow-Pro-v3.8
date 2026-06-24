"""CLI entry point to restore a TaxFlow Pro database backup.

Usage:
    python scripts/restore.py --backup-dir DIR --target-path PATH
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow imports from the project root when running from scripts/ directory.
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root))

from backend.local.backup import restore_db, BackupError
from backend.security.path_safety import safe_path


def main():
    parser = argparse.ArgumentParser(description="Restore TaxFlow Pro database backup")
    parser.add_argument(
        "--backup-dir",
        required=True,
        help="Directory containing the backup manifest.json and database file",
    )
    parser.add_argument(
        "--target-path",
        required=True,
        help="Destination path for the restored database",
    )
    parser.add_argument(
        "--plaintext",
        action="store_true",
        help="Allow restoring an unencrypted plaintext backup (deprecated)",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    try:
        backup_dir = safe_path(project_root, args.backup_dir, must_exist=True)
        target_path = safe_path(project_root, args.target_path)
    except ValueError as exc:
        raise SystemExit(f"Invalid path: {exc}") from exc

    try:
        restored_path = restore_db(str(backup_dir), str(target_path), plaintext=args.plaintext)
    except BackupError as exc:
        raise SystemExit(f"Restore failed: {exc}")

    print(restored_path)


if __name__ == "__main__":
    main()
