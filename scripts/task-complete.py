"""Update shared project state files when a task is completed.

Usage:
    python scripts/task-complete.py TASK-038.10

This script:
1. Marks the task complete in shared/tasks/TASK-038-SUBTASKS.md.
2. Adds a bullet under the correct section in CHANGES.md if a draft exists.
3. Updates docs/TODO_FIRST.md if the task maps to a Phase 3 gap.

Use from inside a task handoff to avoid manual admin work.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TASK_TO_TODO = {
    "TASK-038.1": "3.3",
    "TASK-038.2": "3.8",
    "TASK-038.3": "3.4b",
    "TASK-038.4": "3.4e",
    "TASK-038.5": "3.4a",
    "TASK-038.6": "3.5",
    "TASK-038.7": "3.2",
    "TASK-038.8": "3.1",
    "TASK-038.9": "3.6",
    "TASK-038.10": "3.7",
    "TASK-038.11": "3.4",
    "TASK-038.12": "3.9",
    "TASK-038.13": "3.10",
    "TASK-038.14": "3.11",
}


def mark_subtask_complete(task: str) -> None:
    path = PROJECT_ROOT / "shared" / "tasks" / "TASK-038-SUBTASKS.md"
    if not path.exists():
        print(f"WARNING: {path} not found", file=sys.stderr)
        return
    text = path.read_text(encoding="utf-8")
    # Mark the task line complete if it is not already.
    pattern = rf"(\*\*Task\*\*:\s*{re.escape(task)}.*?)\b(In Progress|Pending|Not started)\b"
    if re.search(pattern, text):
        text = re.sub(pattern, r"\1✅ Complete", text, count=1)
        path.write_text(text, encoding="utf-8")
        print(f"Marked {task} complete in {path}")
    else:
        print(f"No pending line found for {task} in {path}")


def update_todo_first(task: str) -> None:
    gap = TASK_TO_TODO.get(task)
    if not gap:
        return
    path = PROJECT_ROOT / "docs" / "TODO_FIRST.md"
    if not path.exists():
        print(f"WARNING: {path} not found", file=sys.stderr)
        return
    text = path.read_text(encoding="utf-8")
    # Look for a line like "3.7 Local user/auth system ..." and append ✅ if missing.
    pattern = rf"(\*\*{re.escape(gap)}\b.*?)\b(⏳\s*Pending|🔄\s*In\s*Progress)"
    if re.search(pattern, text):
        text = re.sub(pattern, r"\1✅ Complete", text, count=1)
        path.write_text(text, encoding="utf-8")
        print(f"Marked {gap} complete in {path}")
    else:
        print(f"No pending entry for {gap} in {path}")


def append_changes(task: str) -> None:
    """Append a minimal CHANGES.md section if a draft file exists."""
    changes_path = PROJECT_ROOT / "CHANGES.md"
    draft_path = PROJECT_ROOT / "audit_output" / "security_sprint_changes_draft.md"
    if not draft_path.exists():
        return
    draft_text = draft_path.read_text(encoding="utf-8")
    section_map = {
        "TASK-036": "36.",
        "TASK-037": "37.",
        "TASK-038-ENTROPY": "38.",
        "TASK-039": "39.",
    }
    prefix = section_map.get(task)
    if not prefix:
        return
    # Extract the section header and body for the prefix.
    pattern = rf"(##\s*{re.escape(prefix)}.*?(?=##\s*\d+\.|\Z))"
    match = re.search(pattern, draft_text, re.DOTALL)
    if not match:
        print(f"WARNING: No {prefix} section found in draft", file=sys.stderr)
        return
    section = match.group(1).strip()
    if not changes_path.exists():
        changes_path.write_text(f"# TaxFlow Pro Change Log\n\n{section}\n", encoding="utf-8")
        print(f"Created {changes_path} with {prefix} section")
        return
    text = changes_path.read_text(encoding="utf-8")
    # Avoid duplicate insertions.
    if section.splitlines()[0] in text:
        print(f"{prefix} section already in CHANGES.md")
        return
    # Insert after the top header.
    if text.startswith("# "):
        first_blank = text.find("\n\n")
        insert_at = first_blank + 2 if first_blank != -1 else text.find("\n") + 1
        text = text[:insert_at] + section + "\n\n" + text[insert_at:]
    else:
        text = section + "\n\n" + text
    changes_path.write_text(text, encoding="utf-8")
    print(f"Inserted {prefix} section into CHANGES.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update project state after task completion")
    parser.add_argument("task", help="Task label (e.g., TASK-038.10)")
    args = parser.parse_args()

    mark_subtask_complete(args.task)
    update_todo_first(args.task)
    append_changes(args.task)


if __name__ == "__main__":
    main()
