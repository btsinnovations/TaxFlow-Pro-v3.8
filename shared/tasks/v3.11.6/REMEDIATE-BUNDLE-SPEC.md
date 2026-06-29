# V3.11.6 Remediation — Orchestrator Bundle Spec

## Summary
This document bundles the six remediation tracks into a coherent workflow for Jane Clawd. Tracks are grouped by theme and dependency to minimize rebase churn and maximize parallel work.

## Bundle Groupings

### Bundle A — Double-Entry Foundation (R1 + R2)
**Theme:** GL entries and period close are the two most tightly coupled P0 items.
- **R1** adds GL auto-posting from all transaction sources.
- **R2** closes periods by zeroing income/expense and posting to Retained Earnings.
- **Dependency:** R2 must follow R1 because R2's closing entries operate on GL entries.
- **Execution:** Jane starts R1 first. After R1 merges, Jane rebases R2 and completes it.

### Bundle B — CPA Controls (R3 + R4)
**Theme:** Audit-trail controls and CPA deliverables.
- **R3** locks completed reconciliations and cleared transactions.
- **R4** adds missing tax forms, adjusting entries, and year-end package zip.
- **Dependency:** R4 adjusting entries need `GeneralLedgerEntry.entry_type` enum introduced in R2. R3 can run in parallel with R1/R2 until it needs the enum (only if R3 wants to mark system entries; not required). Keep R3 independent.
- **Execution:** Jane starts R3 in parallel with R1. After R1/R2 merge, Jane rebases R4 and completes it.

### Bundle C — Phase C Operations (R5)
**Theme:** Business operations gaps from Phase C.
- **R5** implements sales tax, mileage log, and vendor-keyed 1099.
- **Dependency:** Needs R1 GL bridge for sales tax auto-posting.
- **Execution:** Jane starts R5 after R1 merges.

### Bundle D — Polish & Trust Signals (R6)
**Theme:** Cleanup, docs, version, Alembic reversibility.
- **R6** fixes downgrade bug, token-fragile test, version.txt, docs, orphaned files, frontend mock cleanup, cash-flow basis option.
- **Dependency:** Run last, after R1-R5 merge, so it captures final schema and can update docs accurately.
- **Execution:** Jane starts R6 only after R1-R5 are merged back to `v3.11.6-dev`.

## Recommended Execution Order

```
Day 1-4:  Jane on R1 (GL Auto-Posting)
Day 3-6:  Jane on R3 (Reconciliation Lock) — in parallel with R1
Day 5-7:  James reviews/merges R1 → Jane rebases R2
Day 6-9:  Jane on R2 (Period Close)
Day 8-12: James reviews/merges R2 → Jane rebases R4
Day 9-14: Jane on R4 (Tax + Adjusting + Year-End)
Day 12-16: James reviews/merges R1/R2/R3 → Jane rebases R5
Day 14-18: Jane on R5 (Phase C Ops)
Day 18-21: James reviews/merges all R1-R5 → Jane starts R6
Day 21-24: Jane on R6 (Cleanup)
Day 24-26: Full regression, docs finalization, RC tag
```

## Communication Rhythm
- Daily progress check-in via `sessions_send` from Jane to James.
- Discord `#taxflow-pro-work` update only at track completion or blocker.
- Each track ends with: SQLite pass/fail, PG pass/fail, frontend build status, list of files changed, blockers.

## Merge Rules
1. No track merges to `v3.11.6-dev` without James review and explicit approval.
2. Each track must pass full SQLite + PostgreSQL regression before merge.
3. Frontend build must pass if any frontend files changed.
4. After each merge, rebase dependent branches.
5. No push to release/`main` branch without separate approval.

## File Inventory
- Master plan: `V3.11.6_REMEDIATION_PLAN.md`
- R1 masterplan: `REMEDIATE-R1-MASTERPLAN.md`
- R2 masterplan: `REMEDIATE-R2-MASTERPLAN.md`
- R3 masterplan: `REMEDIATE-R3-MASTERPLAN.md`
- R4 masterplan: `REMEDIATE-R4-MASTERPLAN.md`
- R5 masterplan: `REMEDIATE-R5-MASTERPLAN.md`
- R6 masterplan: `REMEDIATE-R6-MASTERPLAN.md`
- This bundle spec: `REMEDIATE-BUNDLE-SPEC.md`

## Branches (already pushed to origin)
- `v3.11.6-dev-REMEDIATE-R1-gl-autopost`
- `v3.11.6-dev-REMEDIATE-R2-period-close`
- `v3.11.6-dev-REMEDIATE-R3-reconciliation-lock`
- `v3.11.6-dev-REMEDIATE-R4-tax-and-ye`
- `v3.11.6-dev-REMEDIATE-R5-phase-c-ops`
- `v3.11.6-dev-REMEDIATE-R6-cleanup`

## First Directive to Jane
1. Acknowledge receipt.
2. Start **R1 only**.
3. Read `REMEDIATE-R1-MASTERPLAN.md` and `REMEDIATE-BUNDLE-SPEC.md`.
4. Confirm no work begins on R2-R6 until R1 is merged and she receives explicit next directive.
