# TASK-001: TaxFlow Pro v3.9.1 Gap Audit

## Status
Assigned → In Progress

## Goal
Audit the current `TaxFlow-Pro-v3.9` build against the v3.9 hardening roadmap and produce a v3.9.1-specific punchlist that becomes the foundation for the v3.9.1 release.

## Reference Roadmap
`projects/TaxFlow-Pro/taxflow-pro-v3.8-gap-analysis.md` — this is the v3.9 hardening plan.

## Current Build
`projects/TaxFlow-Pro/TaxFlow-Pro-v3.9/`

## Scope of Audit

### 1. Security / Auth
- [ ] Verify current auth implementation (JWT vs opaque tokens vs hybrid)
- [ ] Check for session store / token revocation
- [ ] Check for hardcoded SECRET_KEY fallback
- [ ] Check SQLCipher or other database-level encryption status
- [ ] Check lazy engine creation vs import-time engine

### 2. Frontend
- [ ] Grep for `<PlaceholderPage` / placeholder components
- [ ] Check for mock API files / ghost routes
- [ ] Verify LoginModal/AuthContext/useAPI integration with backend boot/login flow

### 3. Dependencies / CI
- [ ] Audit `requirements.txt`: unused deps, dev/prod split, pinned versions, missing `sqlcipher3`
- [ ] Check for `.github/workflows/tests.yml`
- [ ] Check for `.env.example`

### 4. Parsers
- [ ] Inventory institution parsers in `backend/parsers/` and `phase3_pipeline/parsers/`
- [ ] Check Chime checking parser support
- [ ] Check TD Bank credit parser support
- [ ] Check Cash App detection improvements
- [ ] Check EdFed credit fixtures
- [ ] Check Queensborough National Bank parser presence
- [ ] Document any parser regression test fixtures

### 5. Services / Upstream Merge Decisions
- [ ] Check status of `backend/services/depreciation.py`, `ofx_client.py`, `audit_trail.py`
- [ ] Document whether each is ported, gated, or dropped

### 6. Tests
- [ ] Run `python -m pytest backend/tests/ tests/ -v`
- [ ] Document actual pass/fail counts
- [ ] Check `backend/tests/test_rls.py` status

## Deliverables
1. `/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9/docs/v3.9.1-tasks/v3.9.1-gap-audit-report.md`
2. `/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9/docs/v3.9.1-roadmap.md` — prioritized v3.9.1 punchlist

## Handoff Format
When complete, comment with:
- Summary of findings
- Exact file paths for deliverables
- Test command output
- Known blockers or open questions
- Recommended next task IDs

## Role Assignment
- Builder/Researcher: Jane Clawd
- Reviewer/Validator: James Clawd (orchestrator) + optional second reviewer
