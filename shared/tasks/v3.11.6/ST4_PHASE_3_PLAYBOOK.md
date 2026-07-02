# ST4 Phase 3 — Frontend DOM, Memory, & UI Edge Cases

**Branch:** `v3.11.6-dev`  
**Target:** TaxFlow Pro v3.11.6  
**Date:** 2026-07-01  
**Owner:** Jane Clawd (execution) / James Clawd (planning)

---

## Objective
Prove the TaxFlow Pro frontend survives hostile rendering and interaction patterns:
1. **Massive DOM rendering** (10,000+ GL rows)
2. **State thrashing / memory leaks** (50 modals × 100 cycles)
3. **Localization & layout breaking** (RTL, German compound words, CJK characters, PDF export)

---

## Frontend Architecture Notes

- React 19 + Vite + React Router 7.
- UI library: Radix primitives + Tailwind.
- Tables: `@tanstack/react-table`.
- General Ledger Manager: `frontend/src/components/v3.11/GLManager.tsx`, route `/gl`.
- Reports Center: `frontend/src/components/v3.11/ReportsCenter.tsx`, route `/reports`.
- Auth context: `frontend/src/context/AuthContext.tsx`.
- API hooks: `frontend/src/hooks/useAPI.ts` and `useAPIExtensions.ts`.
- No dedicated i18n library detected; localization test will verify graceful degradation.

---

## Test Environment

- **Backend:** run `python -m backend.api` on `http://localhost:8000` with `DATABASE_URL` pointing at a fresh PostgreSQL test DB.
- **Frontend dev server:** `npm run dev` on `http://localhost:5173`.
- **Browser automation:** Playwright Chromium via `frontend/package.json` (`@playwright/test` is installed).

### Required env (PowerShell)

```powershell
cd "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9"
$env:DATABASE_URL = "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_stress_4_p3"
$env:TAXFLOW_SINGLE_USER = "false"
```

---

## Database Setup

Run **before** any Phase 3 sub-phase:

```powershell
cd "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9"
$env:PYTHONPATH = "."
$env:DATABASE_URL = "postgresql://taxflow_test:taxflow_test@localhost:5433/taxflow_stress_4_p3"
python st4_p3_seed.py
```

This creates:
- One tenant (`Phase 3 Tenant`).
- One master user (`phase3` / `password`).
- 10 GL accounts.
- **10,000 general-ledger entries** across those accounts.
- 200 categorized transactions for PDF/localization tests.

---

## Sub-Phase 3.1 — Massive DOM Rendering

**Script:** `st4_p3_1_dom_massive.py`

### Steps
1. Seed DB (`st4_p3_seed.py`).
2. Start frontend dev server (`npm run dev`).
3. Playwright logs in via `/gl` route.
4. Measures initial render time and JS heap after table loads.
5. Captures browser console errors / crashed tab indicator.

### Success Criteria
- Page loads without browser crash.
- No `out of memory` or `Maximum call stack size exceeded` console errors.
- Render completes in <30 s.
- DOM node count reported in output.

### Notes
- The current `GLManager` loads all entries into a single HTML `<Table>` with no virtualization. This test will likely reveal a rendering bottleneck.
- Do **not** attempt to fix the frontend during this test. Log findings and report.

---

## Sub-Phase 3.2 — State Thrashing / Memory Leaks

**Script:** `st4_p3_2_memory_leak.py`

### Steps
1. Log in.
2. Navigate to `/clients` (uses `ClientModal`) or `/accounts` (uses `AccountModal`).
3. Open and close a modal 50 times, 100 cycles = 5,000 open/close events.
4. Force garbage collection via `window.gc()` if available (launch Chromium with `--js-flags=--expose-gc`).
5. Record JS heap size at start, mid-point, and end.

### Success Criteria
- Heap size plateaus (no continuous linear growth).
- No leaked `setInterval`/`setTimeout` warnings in console.
- App remains responsive after 5,000 modal cycles.

---

## Sub-Phase 3.3 — Localization & Layout Breaking

**Script:** `st4_p3_3_localization.py`

### Steps
1. Seed DB with CJK/German descriptions.
2. Log in, navigate to `/reports`.
3. Trigger PDF export on a report containing mutated descriptions.
4. Flip `<html dir="rtl">` via browser evaluate and screenshot the reports page.
5. Capture any truncated text, overflow, or console font errors.

### Success Criteria
- No 500 from PDF generation endpoint.
- No browser console crash.
- RTL layout does not hide primary action buttons.
- CJK/German text renders without mojibake.

---

## File Inventory for Jane

| File | Purpose |
|---|---|
| `st4_p3_seed.py` | Creates fresh DB + 10k GL entries + CJK/German transactions |
| `st4_p3_1_dom_massive.py` | Sub-phase 3.1 browser automation |
| `st4_p3_2_memory_leak.py` | Sub-phase 3.2 modal thrashing |
| `st4_p3_3_localization.py` | Sub-phase 3.3 RTL / CJK / PDF |
| `ST4_PHASE_3_PLAYBOOK.md` | This document |

---

## Governance

- **No production code changes on failure.** Log, screenshot, and report.
- **Resource monitoring:** Abort if host RAM >85% or a browser tab crashes repeatedly.
- **No commits/pushes for ST4 scripts.** These are local test artifacts.
- **Subagent restriction:** Phase 3 browser tests must run via direct CLI in the main session.

---

## Expected Verdict

Likely findings:
1. `GLManager` will struggle with 10k unvirtualized rows.
2. Radix Dialogs should clean up cleanly, but any global event listeners not attached to React lifecycle may leak.
3. CJK/RTL may expose layout assumptions in Tailwind utility classes (e.g., hardcoded `ml-*` instead of logical properties).

Report should flag each finding with severity and recommend fixes (e.g., virtualized table, `dir`-aware CSS, paginated GL endpoint).
