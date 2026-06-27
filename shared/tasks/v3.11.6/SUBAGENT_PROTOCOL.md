# TaxFlow Pro v3.11.6 — Subagent Protocol

**Branch:** `v3.11.6-dev`  
**Goal:** Execute 7 bundles in parallel where possible while maintaining quality and avoiding branch chaos.

---

## 1. Subagent Roles

| Role | Model | Responsibility |
|------|-------|----------------|
| **Builder** | Jane / default | Implement backend/frontend code per bundle spec. |
| **Validator** | glm-5.1 | Review builder output, harden tests, catch edge cases, run packaging smoke tests. |
| **Orchestrator** | James | Approve bundle merges, resolve blockers, decide cuts. |

---

## 2. Bundle Ownership

Each bundle gets **exactly one builder subagent** at a time. No two subagents edit the same bundle without orchestrator handoff.

| Bundle | Builder | Validator | Merge Gate |
|--------|---------|-----------|------------|
| B1 Foundation | TBD | glm-5.1 | James |
| B2 Transaction Engine | TBD | glm-5.1 | James |
| B3 Assets/Liabilities/FX | TBD | glm-5.1 | James |
| B4 Financial Operations | TBD | glm-5.1 | James |
| B5 Invoicing/AP/AR | TBD | glm-5.1 | James |
| B6 Frontend UI | TBD | glm-5.1 | James |
| B7 Packaging/Hardening | TBD | glm-5.1 | James |

---

## 3. Branch Discipline

- **Only one active branch:** `v3.11.6-dev`.
- Each subagent works on a **local feature branch** named `v3.11.6-dev-BUNDLE-{id}-{short-desc}`.
- Subagent **must rebase on latest `origin/v3.11.6-dev` daily**.
- Subagent **must not force-push `v3.11.6-dev`**.
- Subagent **must not tag or release**.

---

## 4. Commit Rules

- Commit early and often.
- Commit messages follow: `type(scope): description`.
- Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.
- Example: `feat(v3.11.6/B1): add COA seed endpoint with tenant scoping`.
- Each commit must keep the existing test suite green.
- WIP commits allowed during development; rebase/squash before merge request.

---

## 5. Test Mandates

Before declaring a bundle complete, the builder must:

1. Add/update unit tests for every new public function/endpoint.
2. Run the bundle's dedicated test files and confirm **0 failures**.
3. Run `python -m pytest backend/tests/test_api.py backend/tests/test_version.py -q` and confirm green.
4. If frontend changed, run `cd frontend && npm run build` with **0 TypeScript errors**.
5. Add/update Storybook or component smoke tests where feasible.

Validator must:

1. Re-run all bundle tests independently.
2. Add at least one negative / edge-case test per endpoint.
3. Verify tenant isolation is tested.
4. Confirm no new warnings/errors in launcher.log for the affected paths.

---

## 6. Merge Gate

A bundle may only be merged to `v3.11.6-dev` after:

1. Builder reports completion with test output.
2. Validator reviews and approves.
3. Orchestrator (James) approves via explicit "merge BUNDLE-X" directive.
4. CI passes on the feature branch (if CI is configured).

The orchestrator will perform the actual merge. Subagents do **not** merge their own work.

---

## 7. Blocker Escalation

- Technical blockers must be reported within **1 hour** of discovery.
- Report format: `BUNDLE-X BLOCKER: <one-line summary> | Impact: <what is stuck> | Options: <A/B/C>`.
- Do not silently pivot or change scope. Wait for orchestrator decision.

---

## 8. Communication Rules

- Status updates go to the orchestrator via `sessions_send`.
- Human-readable summaries go to Discord `#taxflow-pro-work` only when orchestrator asks.
- No agent-to-agent @mentions in Discord.
- No raw console dumps in status reports; summarize and attach logs as files.

---

## 9. Scope Cuts (Pre-Approved Fallbacks)

If a bundle is slipping or blocked, orchestrator may invoke one of these cuts without restarting planning:

- **B1.03 PostgreSQL RLS** → keep SQLite app-level scoping; move Postgres RLS to v3.11.7.
- **B3.04 Multi-Currency** → store foreign amount only; conversion reports to v3.11.7.
- **B7.02 macOS `.app`** → defer to v3.11.7 if no macOS host available.
- **B7.03 Trust signals** → document-only, same as v3.11.5.

---

## 10. Definition of v3.11.6 Done

- All active bundles merged to `v3.11.6-dev`.
- Full backend test suite: **0 failures**.
- Frontend build: **0 TypeScript errors**.
- Windows `.exe` clean install smoke test passes.
- Ubuntu `.deb` clean install smoke test passes.
- `CHANGES.md` Section 70+ updated.
- Version bumped to `3.11.6`.
- Tag `v3.11.6` created and pushed.
- Installers uploaded to GitHub Release.
