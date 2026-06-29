:warning: **Assigned to Jane** — scaffold committed by James; implementation completion delegated.

# Frontend → Backend Coverage Build Masterplan

## Goal
Eliminate the backend-only router gap identified in `BACKEND_FRONTEND_COVERAGE_MAP.md` by adding frontend consumers (pages, sections, API hooks, and navigation) for every backend module that currently has no UI.

## Current State
- 197 backend endpoints across 37 router modules.
- Only ~14 endpoints have explicit frontend callers in `frontend/src/hooks/useAPI.ts` and components.
- 25+ modules are backend-only (no UI routes, no hooks, no sections).

## Scope
Build minimal-but-complete frontend consumers for the following uncovered / under-covered modules:

1. **Audit** — `/api/audit/*`
2. **Backup** — `/api/backup/*`
3. **Clients** — `/api/clients/*` (exists in landing section but missing route/page)
4. **COA** — `/api/coa/*`
5. **Dashboard** — `/api/dashboard/*` (stats exist but health does not)
6. **Depreciation** — `/api/depreciation/*`
7. **Export** — `/api/export/*`
8. **Flags** — `/api/flags/*`
9. **GL** — `/api/gl/*`
10. **Health** — `/api/health/*`
11. **Imports** — `/api/imports/*`
12. **Investments** — `/api/investments/*`
13. **Invoicing** — `/api/invoicing/*`
14. **Liabilities** — `/api/liabilities/*`
15. **Mileage** — `/api/mileage/*`
16. **Periods** — `/api/periods/*`
17. **Rules** — `/api/rules/*`
18. **Sales Tax** — `/api/sales_tax/*`
19. **Tax** — `/api/tax/*`
20. **Upload** — `/api/upload/*` (frontend section exists but no dedicated route)
21. **Vendors** — `/api/vendors/*`
22. **Year End** — `/api/year_end/*`

## Out of Scope
- `/api/tests/*` — intentionally dev-only, already wired to TestSuite section.
- `/api/ml/*` — already wired to MLTraining section.

## Deliverables

### API Layer
- `frontend/src/hooks/useAPIExtensions.ts` — typed fetch wrappers for every module above.
- Extend `frontend/src/hooks/useAPI.ts` exports to include the new wrappers.

### Page/Module Components
Each module gets a `ModuleShell`-based page in `frontend/src/components/v3.11/`:
- `<AuditManager />`
- `<BackupManager />`
- `<ClientManager />`
- `<COAManager />` (already exported from accounts; ensure it consumes `/api/coa`)
- `<DashboardHealth />`
- `<DepreciationManager />`
- `<ExportManager />`
- `<FlagManager />`
- `<GLManager />`
- `<ImportsManager />`
- `<InvestmentsManager />`
- `<InvoicingManager />` (rename `InvoicingAPAR` to `InvoicingManager` or create new)
- `<LiabilitiesManager />` (rename `LiabilitiesInvestments` or create new)
- `<MileageLog />`
- `<PeriodManager />`
- `<RuleManager />`
- `<SalesTaxManager />`
- `<TaxManager />`
- `<UploadManager />`
- `<VendorManager />`
- `<YearEndManager />`

### Routing
- Update `frontend/src/App.tsx` to add `<Route>` entries for each new module.

### Navigation
- Update `frontend/src/sections/Navigation.tsx` with links to new modules (desktop + mobile).

### Index Exports
- Update `frontend/src/components/v3.11/index.ts` to export all new modules.

## Acceptance Criteria
1. `npm run build` completes without errors.
2. `npm run test` passes existing frontend tests (or new tests are added for new modules).
3. Every route in the new coverage map resolves to a component.
4. Every new module calls at least one backend endpoint from its area.
5. Navigation lists all major modules in a sensible grouping.
6. Re-run `BACKEND_FRONTEND_COVERAGE_MAP.json` generation and confirm coverage rises materially (target: 80+ covered endpoints).

## Verification
```bash
cd frontend
npm run build
npm run test
python ../shared/tasks/v3.11.6/_build_coverage.py
```

## Handoff
- All scaffold files already exist after James's commit.
- Jane implements the hooks, wires components to real endpoints, adds routes/navigation, and runs verification.
- Report back with coverage delta, build/test status, and any blockers.
