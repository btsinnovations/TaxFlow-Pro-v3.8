# TaxFlow Pro v3.11.6 — Post-B4/B5 Roadmap Preview

This document previews what comes after Tracks 6 and 7 are merged. It is not yet a masterplan; it is context for the B4/B5 design so we avoid painting into a corner.

---

## Phase 4 — Frontend UI Shell (B6)

Once B4 and B5 backends are solid, B6 builds the user interface.

| Module | Depends on |
|--------|------------|
| TanStack Table + register scaffolding | B2 register endpoints |
| Unified register component | B2 transactions, splits, status |
| COA tree component | B1 COA endpoints |
| Reports center component | B4 reports endpoints |
| Reconciliation component | B4 reconciliation endpoints |
| Tax export component | B4 tax export endpoints |
| Inventory component | B3 inventory endpoints |
| Profile roles UI | B1 profiles/roles endpoints |

**Key frontend decisions to avoid blocking now:**
- Reports and reconciliation endpoints must return stable JSON shapes (already in API contract)
- Register component needs pagination, filtering, sorting, and bulk actions from B2
- Keep COA numbers as integers; frontend can format them with leading zeros if desired

---

## Phase 5 — Packaging & Platform Hardening (B7)

Deferred hardening from v3.11.5.

| Module | Details |
|--------|---------|
| B7.01 Single-instance enforcement | Bind port 8000; detect existing process on Windows + Ubuntu |
| B7.02 macOS `.app` / DMG | Py2app + create-dmg smoke test |
| B7.03 Staged trust signals | Windows Defender submission + OV cert; Linux GPG-sign `.deb`; Apple Developer + notarization deferred until public distribution |

**Why this is late in the cycle:** core bookkeeping functionality must be stable before packaging final builds.

---

## Phase 6 — Validation + Tag (Release)

- Full test suite green (`pytest backend/tests tests`)
- Installer smoke tests on Windows and Ubuntu
- Version bump to `3.11.6` across backend, frontend, package metadata, and docs
- `CHANGES.md` Section 70+ documents all v3.11.6 work
- Git tag `v3.11.6` on `v3.11.6-dev` (or release branch)

---

## Phase 7 — B8 Full Bank Parser Expansion

Scrape DocuClipper's full supported-banks list and implement dedicated parsers for all remaining institutions (100+). The 23 parsers already in B8 Phase 1 are the research-derived core.

**Strategy:**
- Scrape the list once and store it in `shared/tasks/v3.11.6/DOCUCLIPPER_BANKS.json`
- Group institutions by statement layout family (CSV-like, OFX-like, PDF table, credit-card style)
- Implement parsers by family, then specialize per institution
- Add synthetic fixtures for each new institution
- Expand `test_bank_parsers.py` to cover the full list

**Why this is last:** it is high volume and low risk of breaking existing bookkeeping modules.

---

## Ordering Summary

```
Phase 1: B1 Foundation          ✅ Done
Phase 2: B2 + B3 Engine         ✅ Done
Phase 3: B4 + B5 Operations   ✅ Done
Phase 4: B6 Frontend            ✅ Done
Phase 4.5: PostgreSQL RLS Hardening ✅ Done
Phase 5: B7 Packaging/Hardening → Next
Phase 6: Validation + Tag        → after Phase 5
Phase 7: B8 Full Parser Expansion → end of cycle
```

---

## Open Questions for Josh

1. Should B5 invoice payments auto-create register transactions, or stay as standalone A/R records until reconciliation?
2. Should B4 tax exports include K-1 support, or only Schedule C / 1099 for this cycle?
3. Should B6 frontend be built in the same branch as its backend, or kept as separate frontend-only tracks?
4. Is B8 full 100+ parser expansion a hard release gate, or can it ship after v3.11.6 if needed?
