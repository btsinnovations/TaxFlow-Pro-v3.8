"""Scan all alembic migration downgrades for non-idempotent drop_index/drop_table calls."""
import os
import re

migrations_dir = "alembic/versions"

for fname in sorted(os.listdir(migrations_dir)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(migrations_dir, fname)
    with open(fpath, "r") as f:
        content = f.read()
    
    # Find downgrade function
    downgrade_match = re.search(r'def downgrade\(\).*?(?=\ndef |\Z)', content, re.DOTALL)
    if not downgrade_match:
        continue
    downgrade_code = downgrade_match.group(0)
    
    # Look for op.drop_index without IF EXISTS or try/except
    lines = downgrade_code.split("\n")
    issues = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "op.drop_index" in stripped and "IF EXISTS" not in stripped and "try" not in stripped:
            issues.append(f"  line {i}: {stripped}")
        if "op.drop_table" in stripped and "IF EXISTS" not in stripped and "try" not in stripped:
            issues.append(f"  line {i}: {stripped}")
    
    if issues:
        print(f"\n{fname}:")
        for issue in issues:
            print(issue)