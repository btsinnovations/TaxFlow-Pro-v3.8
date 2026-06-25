# TaxFlow Pro — Updated Release Roadmap

**Project:** `~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9`  
**Date:** 2026-06-25  
**Authority:** Josh directive — skip v3.9.2/v3.10 hardening/packaging, jump directly to v3.11.

---

## New Release Sequence

| Release | Focus | Spec | Task Tracker | Starts After |
|---------|-------|------|--------------|--------------|
| **v3.11** | Core bookkeeping platform + parser expansion + tax rules engine + OFX/live feed + polished export UI | `shared/specs/v3.11-bookkeeping-spec-UPDATED.md` | `shared/tasks/v3.11/V3.11-TASKS-UPDATED.md` | v3.9 stable |
| **v3.11.5** | Security hardening + desktop packaging (packaging work from upstream v3.10.0, hardening from v3.9.2/v3.10) | TBD | TBD | v3.11 stable |

**Removed from sequence:**
- v3.9.2 security hardening (merged into v3.11.5)
- v3.10 desktop packaging + tooling replacements (merged into v3.11.5)

---

## Scope Changes for v3.11

### Added to v3.11

| ID | Feature | Notes |
|----|---------|-------|
| 3.11.PARSER | **All current bank parsers** | Integrate every existing Tier 1+ parser into the release; expand institution coverage beyond current 9. |
| 3.11.TAXRULES | **Tax rules engine search/filter** | Text search + filter UI/API for finding rules by name, pattern, category, priority, account. |
| 3.11.OFX | **OFX / live feed integration** | Optional OFX file import and, where practical, local live bank-feed ingestion. No cloud auth by default. |
| 3.11.EXPORTUI | **Polished export UI** | Enable format selection only when statements processed; clear disabled hints; remove stale labels like "(HomeBank)". |

### Removed / Deferred to v3.11.5

| Original Scope | Reason |
|----------------|--------|
| Security hardening (v3.9.2 tasks) | Consolidated into v3.11.5 |
| Desktop packaging / vendored libraries (v3.10 tasks) | Consolidated into v3.11.5 |
| Offline library integration / vendored deps (Tesseract, Poppler) | Out of v3.11; revisit in v3.11.5 if needed |
| RLS / multi-tenant hardening | v3.11.5 |
| macOS / Linux packaging | v3.11.5 |

### Kept from Prior v3.11 Spec

- 13 must-have bookkeeping modules (chart of accounts, register, recurring, checks, loans/investments, inventory, multi-currency, reconciliation, tax exports, reports, budget, invoicing).
- Unified register-style UI (TanStack Table v8, shadcn/ui, Recharts).
- v3.10 → v3.11 backup import wizard.
- Alembic migration for COA + new tables.
- All-new modules must have tests.

---

## Exit Criteria for v3.11

1. All 13 bookkeeping modules implemented and tested.
2. Unified register UI functional end-to-end.
3. All existing bank parsers integrated and passing parser tests.
4. Tax rules engine search/filter works in UI and API.
5. OFX import / live-feed path functional (minimum: OFX file import; live feed if feasible without cloud auth).
6. Export UI polished per 3.11.EXPORTUI.
7. v3.10 backup imports cleanly into v3.11.
8. Full test suite passes.

---

## Next Actions

1. Update `v3.11-bookkeeping-spec.md` with added scope.
2. Update `V3.11-TASKS.md` with new parser, tax rules, OFX, and export UI tasks.
3. Cut `v3.11-dev` branch from v3.9 stable baseline.
4. Assign initial tasks to Jane.

---

## Notes

- Upstream `btsinnovations/TaxFlow-Pro-v3.8` has already shipped v3.10.0 packaging. That work can be reused when v3.11.5 begins.
- v3.11 is now a **feature-forward release**, not a hardening release.
