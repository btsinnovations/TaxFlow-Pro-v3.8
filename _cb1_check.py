"""CB1 verification: test alembic up/down/up on fresh SQLite.
Uses a temporary alembic.ini override to point at a fresh test DB."""
import sqlite3
import subprocess
import sys
import os
import shutil

PROJECT = os.path.dirname(os.path.abspath(__file__))
test_db = os.path.join(PROJECT, "test_cb1_fresh.db")
test_ini = os.path.join(PROJECT, "test_alembic.ini")

# Step 0: Check existing taxflow.db state
print("=== Step 0: Check existing taxflow.db ===")
taxflow_db = os.path.join(PROJECT, "taxflow.db")
if os.path.exists(taxflow_db):
    conn = sqlite3.connect(taxflow_db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables in taxflow.db: {tables}")
    try:
        ver = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        print(f"Alembic version: {ver}")
    except Exception as e:
        print(f"No alembic_version table: {e}")
    conn.close()
else:
    print("taxflow.db does not exist")

# Create a temporary alembic.ini pointing at our test DB
with open(os.path.join(PROJECT, "alembic.ini"), "r") as f:
    ini_content = f.read()

# Replace the sqlalchemy.url line
test_ini_content = ini_content.replace(
    "sqlite:///./taxflow.db",
    f"sqlite:///{test_db.replace(os.sep, '/')}"
)
with open(test_ini, "w") as f:
    f.write(test_ini_content)

def run_alembic(*args):
    """Run alembic with our test config."""
    cmd = [sys.executable, "-m", "alembic", "-c", test_ini] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT)
    return result

try:
    # Step 1: Fresh SQLite — upgrade from scratch
    print("\n=== Step 1: Fresh SQLite alembic upgrade head ===")
    if os.path.exists(test_db):
        os.remove(test_db)

    result = run_alembic("upgrade", "head")
    print(f"Return code: {result.returncode}")
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if "migration" in line.lower() or "upgrade" in line.lower() or "PASS" in line:
                print(f"  {line}")
    if result.returncode != 0:
        # Show last 800 chars of stderr for debugging
        print(f"STDERR (last 800): {result.stderr[-800:]}")
        print("FAIL: upgrade head on fresh SQLite")
        sys.exit(1)

    # Verify tables exist
    conn = sqlite3.connect(test_db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"  Tables created: {len(tables)}")
    ver = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    print(f"  Alembic version: {ver}")
    conn.close()

    # Step 2: Downgrade to base
    print("\n=== Step 2: alembic downgrade base ===")
    result = run_alembic("downgrade", "base")
    print(f"  Return code: {result.returncode}")
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if "migration" in line.lower() or "downgrade" in line.lower():
                print(f"  {line}")
    if result.returncode != 0:
        print(f"STDERR (last 800): {result.stderr[-800:]}")
        print("FAIL: downgrade base on SQLite")
        sys.exit(1)

    # Verify tables are gone
    conn = sqlite3.connect(test_db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"  Tables after downgrade: {len(tables)} -> {tables}")
    conn.close()

    # Step 3: Upgrade head again
    print("\n=== Step 3: alembic upgrade head (second time) ===")
    result = run_alembic("upgrade", "head")
    print(f"  Return code: {result.returncode}")
    if result.stdout:
        for line in result.stdout.strip().split("\n"):
            if "migration" in line.lower() or "upgrade" in line.lower():
                print(f"  {line}")
    if result.returncode != 0:
        print(f"STDERR (last 800): {result.stderr[-800:]}")
        print("FAIL: second upgrade head on SQLite")
        sys.exit(1)

    # Verify tables again
    conn = sqlite3.connect(test_db)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"  Tables after re-upgrade: {len(tables)}")
    ver = conn.execute("SELECT version_num FROM alembic_version").fetchall()
    print(f"  Alembic version: {ver}")
    conn.close()

    print("\n=== CB1 SQLite: PASS ===")

finally:
    # Cleanup
    for f in [test_db, test_ini]:
        if os.path.exists(f):
            os.remove(f)