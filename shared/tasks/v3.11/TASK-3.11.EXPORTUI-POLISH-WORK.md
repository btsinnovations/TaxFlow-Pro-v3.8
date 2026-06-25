# TASK-3.11.EXPORTUI — Polished Export UI

**Owner:** Jane  
**Goal:** Polish the export formats dropdown and related export UI states.

## Current State

- Frontend export dropdown likely has stale "(HomeBank)" label.
- Format options may be enabled even when no statements processed.
- Tests: **missing**

## Files

- Inspect frontend export component (likely `frontend/src/components/export/`).
- `frontend/src/components/export/ExportPanel.tsx` — modify or create.
- `frontend/src/components/upload/ProcessedFiles.tsx` — update if needed.

## Tasks

1. **Remove stale label (3.11.EXPORTUI.01)**
   - Remove "(HomeBank)" text from QIF dropdown option.

2. **Conditional format enablement (3.11.EXPORTUI.02)**
   - Disable format options until at least one statement has been processed.
   - Enable formats that make sense for current data (CSV always, OFX/CSV from statements, QIF if register data exists).

3. **Disabled hint / empty state (3.11.EXPORTUI.03)**
   - When disabled, show hint: "Process a statement to enable OFX/QIF export."
   - Empty state with upload CTA.

4. **Progress/status indicator (3.11.EXPORTUI.04)**
   - Show spinner during export generation.
   - Show success/error toast.

## Tests

- Component tests using React Testing Library or Vitest.
- Snapshot test for export panel states (no data, with data, generating).

## Constraints

- No backend changes unless needed for export generation API.
- Keep UI consistent with shadcn/ui.

## Report

Files changed, test command + result, blockers.
