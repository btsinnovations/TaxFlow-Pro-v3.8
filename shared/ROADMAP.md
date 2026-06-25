# TaxFlow Pro — Release Roadmap

**Project:** `~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9`  
**Active branch:** `v3.9.2-dev` (security hardening in flight)  

## Release Sequence

| Release | Focus | Spec | Task Tracker | Starts After |
|---------|-------|------|--------------|--------------|
| **v3.9.2** | Security hardening (7 tasks already in flight) | project docs + Discord thread | `shared/tasks/v3.9.2/` (to be created) | v3.9.1 stable |
| **v3.10** | Tooling replacements + deeper security hardening | `shared/specs/v3.10-hardening-spec.md` | `shared/tasks/v3.10/V3.10-TASKS.md` | v3.9.2 release tag |
| **v3.11** | Bookkeeping platform expansion | `shared/specs/v3.11-bookkeeping-spec.md` | `shared/tasks/v3.11/V3.11-TASKS.md` | v3.10 release tag |
| **v3.11.5** | Desktop packaging (Electron or Tauri) | TBD | TBD | v3.11 stable |

## Current State

- v3.9.2: TASK-026 crashed mid-edit (relative-path bug). Jane is the builder; weekly usage limit was the blocker. Usage has reset.
- v3.10: Scaffolding complete. 25 tasks created (8 tooling + 17 security).
- v3.11: Scaffolding complete. 13 must-have modules + 8 frontend tasks + 4 global tasks. Existing v3.10 bookkeeping specs rehomed here.

## Team Shape

- **Orchestrator:** James Clawd
- **Builder:** Jane Clawd
- **Reviewer/Validator:** spawn per task as needed

See `agent-team-orchestration` skill for workflow.

## Next Actions

1. Finish v3.9.2 TASK-026 and remaining v3.9.2 tasks.
2. Cut `v3.10-dev` branch from v3.9.2 tag.
3. Begin v3.10.P1 tooling/security tasks.
4. After v3.10 exits, cut `v3.11-dev` and begin bookkeeping expansion.
