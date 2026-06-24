"""SQLCipher feasibility spike for TaxFlow Pro v3.9.1.

This script demonstrates that `sqlcipher3` can create an encrypted SQLite
file that standard `sqlite3` cannot read. It is a research artifact only; do
not use it for production data without review.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile


def _require_sqlcipher3():
    try:
        import sqlcipher3  # type: ignore
        return sqlcipher3
    except ImportError as exc:
        print(f"FAIL: sqlcipher3 is not installed ({exc})")
        print("Install it with: python -m pip install sqlcipher3")
        sys.exit(1)


def main() -> int:
    sqlcipher3 = _require_sqlcipher3()
    key = os.environ.get("TAXFLOW_SQLCIPHER_KEY", "spike-demo-key-123")
    db_path = tempfile.mktemp(suffix="_sqlcipher_spike.db")

    try:
        # 1. Create encrypted database and table.
        conn = sqlcipher3.connect(db_path)
        conn.execute(f"PRAGMA key = '{key}';")
        conn.execute("CREATE TABLE secrets (id INTEGER PRIMARY KEY, value TEXT);")
        conn.execute("INSERT INTO secrets (value) VALUES ('taxflow-encrypted');")
        conn.commit()

        # 2. Read back with the correct key.
        cur = conn.execute("SELECT value FROM secrets;")
        row = cur.fetchone()
        conn.close()

        assert row is not None and row[0] == "taxflow-encrypted"
        print("OK: encrypted write + read succeeded")

        # 3. Verify standard sqlite3 cannot open the file.
        plain = sqlite3.connect(db_path)
        try:
            cur = plain.execute("SELECT value FROM secrets;")
            print(f"FAIL: plain sqlite3 read row: {cur.fetchone()}")
            return 1
        except sqlite3.DatabaseError as exc:
            print(f"OK: plain sqlite3 rejected the file ({exc})")
            return 0
        finally:
            plain.close()
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
