# TASK-3.11.TAXRULES — Tax Rules Engine Search/Filter

**Owner:** Jane  
**Goal:** Add backend search/filter API and frontend UI for the tax rules / categorization rules engine.

## Current State

- `backend/models.py` has `CategorizationRule` table.
- `backend/routers/rules.py` or similar may exist; inspect `backend/api.py`.
- No search/filter endpoint or UI.
- Tests: **missing**

## Files

- `backend/routers/rules.py` — add search/filter endpoint if missing.
- `backend/schemas.py` — add query params schema.
- `backend/tests/test_tax_rules_search.py` — new
- `frontend/src/components/tax/TaxRulesSearch.tsx` — new

## Backend API

`GET /api/tax-rules?query=&form=Schedule+C&line=Advertising&enabled=true&sort=priority&order=desc`

Response: list of `CategorizationRuleOut`.

## Backend Tests Required

1. `test_search_by_name_pattern`
   - Filter by query string matching name or pattern.
2. `test_filter_by_form_and_line`
   - Filter by tax form and line.
3. `test_filter_by_enabled_status`
   - Return only enabled rules.
4. `test_sort_by_priority_date_pattern_length`
   - Sort options: priority, created_at, pattern length.
5. `test_search_empty_state`
   - No matches returns empty list with 200.

## Frontend UI

- Search input with debounce.
- Filters: form, line, enabled status.
- Sort dropdown.
- Results table with edit/delete actions.
- Empty-state message.

## Constraints

- Offline-only.
- Must not slow down on 1000+ rules.

## Report

Files changed, test command + result, blockers.
